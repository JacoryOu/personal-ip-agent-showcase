from pathlib import Path
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
import argparse
import json
import sys
import urllib.request

try:
    import trafilatura
except ImportError:
    trafilatura = None


def extract_content(url=None, html_content=None):
    downloaded = html_content
    effective_url = url

    if not downloaded and url:
        if trafilatura:
            downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            # Fallback simple fetch
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    downloaded = response.read().decode('utf-8', errors='ignore')
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Failed to fetch URL: {str(e)}',
                    'url': url,
                    'text': '',
                }

    if not downloaded:
        return {
            'success': False,
            'error': 'No content or URL provided to extract.',
            'text': '',
        }

    title = ''
    author = ''
    date = ''
    text = ''

    if trafilatura:
        extracted_data = trafilatura.bare_extraction(
            downloaded,
            url=effective_url,
            include_comments=False,
            include_tables=True,
            no_fallback=False
        )
        if extracted_data:
            text = extracted_data.text or ''
            title = extracted_data.title or ''
            author = extracted_data.author or ''
            date = extracted_data.date or ''

    if not title and downloaded:
        import re
        title_match = re.search(r'<title[^>]*>(.*?)</title>', downloaded, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
        if not title:
            h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', downloaded, re.IGNORECASE | re.DOTALL)
            if h1_match:
                title = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()

    if not text:
        # Fallback simple text strip
        import re
        clean_text = re.sub(r'<script[^>]*>.*?</script>', '', downloaded, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<style[^>]*>.*?</style>', '', clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<[^>]+>', ' ', clean_text)
        text = re.sub(r'\s+', ' ', clean_text).strip()

    return {
        'success': True,
        'title': title or 'Untitled Extracted Article',
        'text': text,
        'author': author,
        'date': date,
        'url': effective_url,
        'word_count': len(text),
    }


def main():
    parser = argparse.ArgumentParser(description='Extract clean article text and metadata.')
    parser.add_argument('--url', help='URL of the article')
    parser.add_argument('--html', help='Raw HTML string')
    parser.add_argument('--json', help='JSON string with url or html_content')
    parser.add_argument('--file', help='Path to JSON file with input parameters')
    args = parser.parse_args()

    url = args.url
    html_content = args.html

    if args.file and Path(args.file).exists():
        try:
            payload = json.loads(Path(args.file).read_text(encoding='utf-8'))
            url = payload.get('url', url)
            html_content = payload.get('html_content', html_content)
        except Exception:
            pass

    if args.json:
        try:
            payload = json.loads(args.json)
            url = payload.get('url', url)
            html_content = payload.get('html_content', html_content)
        except Exception:
            pass

    if not url and not html_content and not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read().strip()
            if stdin_data:
                try:
                    payload = json.loads(stdin_data)
                    url = payload.get('url', url)
                    html_content = payload.get('html_content', html_content)
                except Exception:
                    html_content = stdin_data
        except Exception:
            pass

    result = extract_content(url=url, html_content=html_content)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
