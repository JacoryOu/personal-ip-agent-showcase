# -*- coding: utf-8 -*-
"""Gate: the API authentication boundary must not silently regress.

Authentication is declared once, on the aggregating router built by
``app.api.create_private_router()``, so a newly added handler is protected by
default instead of relying on the author remembering ``Depends(get_current_user)``.

This gate verifies that promise from two directions:

* **static** -- every api module is mounted by ``app.api``, the private and
  public aggregates are built with the right factory, and only the designated
  public module may declare a ``public_router``;
* **runtime** -- every ``/api`` route exposed by the real application resolves a
  caller identity, unless the exact ``METHOD path`` pair is listed in
  ``app.api.auth_boundary.PUBLIC_ENDPOINTS``.

Usage::

    python scripts/check_api_auth.py
    python scripts/check_api_auth.py --base main
"""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "backend" / "app" / "api"
API_INIT = API_DIR / "__init__.py"
AUTH_BOUNDARY = API_DIR / "auth_boundary.py"
PUBLIC_MODULE = "private_domain.py"
#: The public surface may be declared by the private_domain module family
#: (the facade plus its split siblings). Anything else still fails closed.
PUBLIC_MODULE_PREFIX = "private_domain"
SKIP_MODULES = {"__init__.py", "auth_boundary.py"}


def _normalise(path: str) -> str:
    return re.sub(r"/+", "/", path if path.startswith("/") else "/" + path)


def _collect_mounted_api_modules(init_tree: ast.Module) -> Set[str]:
    """Compute the transitive ``app.api.*`` mounting closure.

    Route modules are not only imported directly by ``app/api/__init__.py``.
    A facade module (e.g. ``drafts.py``) imports its split siblings
    (``draft_generation.py`` and friends), which contribute their own routers.
    A single-level scan therefore reports genuinely mounted modules as unmounted.
    """
    mounted: Set[str] = set()
    queue: List[ast.Module] = [init_tree]
    seen_paths: Set[Path] = set()

    while queue:
        tree = queue.pop()
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and node.module.startswith("app.api.")
            ):
                continue
            module_name = node.module
            if module_name == "app.api.__init__":
                continue
            stem = module_name.rsplit(".", 1)[-1]
            if stem in mounted:
                continue
            mounted.add(stem)
            child = API_DIR / f"{stem}.py"
            if child.is_file() and child not in seen_paths:
                seen_paths.add(child)
                queue.append(
                    ast.parse(child.read_text(encoding="utf-8"), filename=str(child))
                )
    return mounted


def _check_static() -> List[str]:
    """Checks that do not need the application object."""
    errors: List[str] = []

    init_source = API_INIT.read_text(encoding="utf-8")
    init_tree = ast.parse(init_source, filename=str(API_INIT))

    if "create_private_router" not in init_source:
        errors.append("app/api/__init__.py must build the business aggregate with create_private_router()")
    if "create_public_router" not in init_source:
        errors.append("app/api/__init__.py must build the public aggregate with create_public_router()")

    # The private factory must actually depend on the identity resolver.
    boundary_source = AUTH_BOUNDARY.read_text(encoding="utf-8")
    if "Depends(get_current_user)" not in boundary_source:
        errors.append(
            "app/api/auth_boundary.py: create_private_router() must apply Depends(get_current_user)"
        )

    # The private aggregate must not be reachable without a dependency.
    private_aggregate_ok = False
    public_aggregate_ok = False
    for node in ast.walk(init_tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        if not isinstance(node.value.func, ast.Name):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if node.value.func.id == "create_private_router" and target.id == "api_router":
            private_aggregate_ok = True
        if node.value.func.id == "create_public_router" and target.id == "public_endpoints_router":
            public_aggregate_ok = True
    if not private_aggregate_ok:
        errors.append("app/api/__init__.py: api_router must be built by create_private_router()")
    if not public_aggregate_ok:
        errors.append(
            "app/api/__init__.py: public_endpoints_router must be built by create_public_router()"
        )

    mounted = _collect_mounted_api_modules(init_tree)

    for path in sorted(API_DIR.glob("*.py")):
        if path.name in SKIP_MODULES or path.name.startswith("_"):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        declares_public = bool(re.search(r"^public_router\s*=", source, re.MULTILINE))
        if declares_public and path.stem != PUBLIC_MODULE:
            if not (
                path.stem == PUBLIC_MODULE
                or path.stem.startswith(PUBLIC_MODULE_PREFIX)
                or path.stem.startswith(PUBLIC_MODULE_PREFIX + "_")
            ):
                errors.append(
                    f"{rel}: only the {PUBLIC_MODULE} module family may declare a public_router"
                )
        if path.stem not in mounted:
            errors.append(f"{rel}: not mounted by app/api/__init__.py")
    return errors


def _check_runtime() -> List[str]:
    """Walk the real application and require auth on every /api route."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))

    from app.api.auth_boundary import PUBLIC_ENDPOINTS
    from app.core.auth import get_current_user
    from fastapi.routing import APIRoute

    from app.api import api_router, public_endpoints_router
    from app.main import app

    errors: List[str] = []

    def walk(router, prefix: str, inherited_private: bool, out: list) -> None:
        for route in router.routes:
            if isinstance(route, APIRoute):
                out.append((prefix + route.path, route, inherited_private))
            elif hasattr(route, "routes"):
                nested_private = inherited_private or _calls_get_current_user(route)
                walk(route, prefix + getattr(route, "prefix", ""), nested_private, out)

    collected: list = []
    walk(api_router, "", True, collected)
    walk(public_endpoints_router, "", False, collected)

    declared: Set[Tuple[str, str]] = {
        (method.upper(), _normalise(path)) for method, path in PUBLIC_ENDPOINTS
    }

    observed: Set[Tuple[str, str]] = set()
    for path, route, inherited_private in collected:
        full = _normalise(path)
        for method in route.methods or set():
            key = (method.upper(), full)
            if key in observed:
                continue
            observed.add(key)
            authenticated = inherited_private or _route_has_auth(route)
            if authenticated or key in declared:
                continue
            errors.append(
                f"{key[0]} {key[1]} is reachable without authentication and is not "
                "listed in app.api.auth_boundary.PUBLIC_ENDPOINTS"
            )

    # The openapi schema is the ground truth for what is actually exposed.
    for path, item in app.openapi().get("paths", {}).items():
        if not path.startswith("/api"):
            continue
        for method in item:
            observed.add((method.upper(), _normalise(path)))

    for method, path in sorted(declared - observed):
        errors.append(
            f"PUBLIC_ENDPOINTS lists {method} {path} but no such route is exposed by the app"
        )

    # Sanity: the identity resolver used by the factory is the real one.
    if get_current_user is None:
        errors.append("app.core.auth.get_current_user is not importable")

    return errors


def _calls_get_current_user(node) -> bool:
    for sub in ast.walk(node) if isinstance(node, ast.AST) else []:
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == "Depends":
            for arg in sub.args:
                if isinstance(arg, ast.Attribute) and arg.attr == "get_current_user":
                    return True
                if isinstance(arg, ast.Name) and arg.id == "get_current_user":
                    return True
    return False


def _route_has_auth(route) -> bool:
    from app.core.auth import get_current_user

    seen = set()
    stack = [getattr(route, "dependant", None)]
    while stack:
        dependant = stack.pop()
        if dependant is None or id(dependant) in seen:
            continue
        seen.add(id(dependant))
        if getattr(dependant, "call", None) is get_current_user:
            return True
        stack.extend(getattr(dependant, "dependencies", []) or [])
    return False


def _check_base(base: str) -> List[str]:
    try:
        changed = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except Exception:
        return []
    route_files = [f for f in changed if f.startswith("backend/app/api/") and f.endswith(".py")]
    if route_files and "scripts/check_api_auth.py" not in changed:
        return ["route modules changed without touching scripts/check_api_auth.py: " + ", ".join(route_files)]
    return []


def check(base: Optional[str] = None) -> List[str]:
    errors = _check_static() + _check_runtime()
    if base:
        errors.extend(_check_base(base))
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the API authentication boundary.")
    parser.add_argument("--base", help="Optional git base ref for a diff-aware check.")
    args = parser.parse_args()

    errors = check(args.base)
    if errors:
        print("API authentication boundary check FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("API authentication boundary check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

