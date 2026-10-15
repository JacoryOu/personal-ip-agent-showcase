# -*- coding: utf-8 -*-
"""Compatibility facade for the Thinking DNA API.

Shared schemas and helpers live in `app.api.dna_common`; the route handlers
are split across `app.api.dna_extraction`, `app.api.dna_traits` and
`app.api.dna_portability`. The `dna` blueprint name, every route path and every
previously importable public symbol are preserved.
"""

from app.api.dna_common import *  # noqa: F401,F403
from app.api.dna_common import (  # noqa: F401
    AddTraitRequest,
    DeconstructBenchmarkRequest,
    DetectConflictsRequest,
    DialogueClashRequest,
    ImportDNARequest,
    IngestOwnWorkRequest,
    ToggleTraitRequest,
    TraitActionRequest,
    UpdateTraitRequest,
    _trusted_user_id,
    get_diff_agent,
    router,
)

from app.api.dna_extraction import (  # noqa: F401
    deconstruct_benchmark,
    extract_thinking_dna,
    ingest_own_work,
    record_dialogue_clash,
)
from app.api.dna_traits import (  # noqa: F401
    add_custom_cognitive_trait,
    delete_cognitive_trait,
    get_benchmarks,
    get_cognitive_profile,
    get_skills,
    pin_cognitive_trait,
    suppress_cognitive_trait,
    unpin_cognitive_trait,
)
from app.api.dna_portability import (  # noqa: F401
    detect_viewpoint_conflicts,
    export_thinking_dna_json,
    import_thinking_dna_json,
    list_cognitive_traits,
    list_dna_records,
    toggle_cognitive_trait,
    toggle_cognitive_trait_by_id,
    update_cognitive_trait,
)

__all__ = [
    'AddTraitRequest',
    'DeconstructBenchmarkRequest',
    'DetectConflictsRequest',
    'DialogueClashRequest',
    'ImportDNARequest',
    'IngestOwnWorkRequest',
    'ToggleTraitRequest',
    'TraitActionRequest',
    'UpdateTraitRequest',
    '_trusted_user_id',
    'add_custom_cognitive_trait',
    'deconstruct_benchmark',
    'delete_cognitive_trait',
    'detect_viewpoint_conflicts',
    'export_thinking_dna_json',
    'extract_thinking_dna',
    'get_benchmarks',
    'get_cognitive_profile',
    'get_diff_agent',
    'get_skills',
    'import_thinking_dna_json',
    'ingest_own_work',
    'list_cognitive_traits',
    'list_dna_records',
    'pin_cognitive_trait',
    'record_dialogue_clash',
    'router',
    'suppress_cognitive_trait',
    'toggle_cognitive_trait',
    'toggle_cognitive_trait_by_id',
    'unpin_cognitive_trait',
    'update_cognitive_trait',
]
