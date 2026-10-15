from pathlib import Path
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
import argparse
import json
import re


def extract_sentences(text):
    sentences = re.split(r'[\u3002\uff01\uff1f!?\n]+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 6]


def mine_own_work(content):
    sentences = extract_sentences(content)
    
    vocab_candidates = []
    tech_patterns = re.findall(r'[A-Za-z0-9_]{3,}', content)
    unique_tech = list(dict.fromkeys(tech_patterns))[:5]
    if unique_tech:
        joined = ', '.join(unique_tech[:3])
        vocab_candidates.append(f'\u9891\u7e41\u5f15\u7528\u4e13\u4e1a\u672f\u8bed/\u82f1\u6587\u6982\u5ff5\uff1a{joined}')
    
    avg_len = sum(len(s) for s in sentences) / max(1, len(sentences))
    if avg_len < 25:
        vocab_candidates.append('\u504f\u597d\u77ed\u5c0f\u7cbe\u608d\u7684\u9648\u8ff0\u53e5\uff0c\u8282\u594f\u7d27\u51d1')
    else:
        vocab_candidates.append('\u503e\u5411\u4e8e\u4f7f\u7528\u590d\u5408\u957f\u53e5\u8fdb\u884c\u7f2c\u5bc6\u63a8\u6f14')

    if any(k in content for k in ['\u672c\u8d28\u4e0a', '\u6838\u5fc3\u5728\u4e8e', '\u5e95\u5c42\u903b\u8f91', '\u7b2c\u4e00\u6027\u539f\u7406']):
        vocab_candidates.append('\u4e60\u60ef\u4f7f\u7528\u201c\u5e95\u5c42\u903b\u8f91/\u672c\u8d28\u4e0a\u201d\u7b49\u6eaf\u6e90\u578b\u5f15\u5bfc\u8bcd')
    if any(k in content for k in ['\u6bcb\u5eb8\u7f6e\u7591', '\u7edd\u975e', '\u76f8\u53cd', '\u5b9e\u9645\u4e0a']):
        vocab_candidates.append('\u5584\u7528\u80af\u5b9a\u4e0e\u53cd\u8f6c\u5bf9\u6bd4\u8bcd\u5f3a\u5316\u8bba\u65ad')

    logic_candidates = []
    if any(k in content for k in ['\u9996\u5148', '\u5176\u6b21', '\u518d\u6b21', '\u6700\u540e', '1.', '2.', '3.']):
        logic_candidates.append('\u591a\u5c42\u6b21\u679a\u4e3e\u5f52\u7eb3\u6cd5\uff08\u4ee5\u6e05\u6670\u7f16\u53f7\u6216\u65f6\u5e8f\u63a8\u8fdb\uff09')
    elif any(k in content for k in ['\u867d\u7136', '\u4f46\u662f', '\u7136\u800c', '\u8f6c\u6298']):
        logic_candidates.append('\u6b63\u53cd\u5408\u5bf9\u7acb\u7edf\u4e00\u8fa9\u8bc1\u6cd5\uff08\u5148\u626c\u540e\u6291\u6216\u7834\u7acb\u7ed3\u5408\uff09')
    else:
        logic_candidates.append('\u81ea\u5e95\u5411\u4e0a\u57fa\u4e8e\u4e8b\u5b9e\u76f4\u89c9\u7684\u6eaf\u56e0\u5f52\u7eb3\u6cd5')

    if any(k in content for k in ['\u4f8b\u5982', '\u6bd4\u5982', '\u4ee5\u4ee3\u7801\u4e3a\u4f8b', '\u5b9e\u9645\u573a\u666f\u4e2d']):
        logic_candidates.append('\u5f3a\u8c03\u5de5\u7a0b\u4e0e\u5b9e\u8df5\u843d\u5730\u6848\u4f8b\u4f50\u8bc1')

    values_candidates = []
    for s in sentences:
        if any(k in s for k in ['\u5fc5\u987b', '\u5e94\u5f53', '\u575a\u51b3', '\u53cd\u5bf9', '\u63d0\u5021', '\u771f\u6b63\u7684', '\u6700\u91cd\u8981']):
            if len(s) < 80:
                values_candidates.append(s)
            if len(values_candidates) >= 3:
                break

    if not values_candidates and sentences:
        values_candidates.append(sentences[0])

    return {
        'vocabulary_habits': vocab_candidates[:4],
        'logic_preferences': logic_candidates[:3],
        'core_values': values_candidates[:4],
        'summary': f'\u57fa\u4e8e {len(sentences)} \u4e2a\u5173\u952e\u8bba\u65ad\u5207\u7247\u63d0\u70bc\u7684\u4e2a\u4eba\u601d\u7ef4\u7279\u5f81\u3002',
    }


def mine_benchmark(content):
    sentences = extract_sentences(content)
    total_len = len(content)
    hook = sentences[0] if sentences else '\u5f00\u95e8\u89c1\u5c71\u63d0\u51fa\u95ee\u9898'
    
    stages = [
        '\u60ac\u5ff5/\u75db\u70b9\u5207\u5165\u5f15\u5165\u51b2\u7a81',
        '\u591a\u7ef4\u5256\u6790\u6838\u5fc3\u6839\u56e0\u4e0e\u77db\u76fe',
        '\u7ed9\u51fa\u7834\u5c40\u65b9\u6848\u6216\u7ec8\u5c40\u601d\u8003',
        '\u5347\u534e\u603b\u7ed3\u5e76\u5524\u8d77\u60c5\u7eea\u5171\u9e23',
    ]
    
    emotional_arc = '\u56f0\u60d1/\u7126\u8651 \u2794 \u987f\u609f/\u7406\u6027\u5256\u6790 \u2794 \u7b03\u5b9a/\u8d4b\u80fd\u884c\u52a8'
    if '\u98ce\u9669' in content or '\u8b66\u60d5' in content:
        emotional_arc = '\u5371\u673a\u8b66\u793a \u2794 \u6df1\u5ea6\u6392\u67e5 \u2794 \u907f\u5751\u89e3\u6cd5'

    pacing = '\u524d 20% \u5feb\u901f\u7834\u9898\uff0c\u4e2d\u95f4 60% \u6df1\u5ea6\u5c55\u5f00\u8bba\u636e\uff0c\u540e 20% \u60c5\u611f\u547c\u5e94'

    clash_points = []
    triggers = [
        '\u6beb\u65e0\u7591\u95ee', '\u5f7b\u5e95', '\u5fc5\u7136', '\u552f\u4e00',
        '\u6c38\u8fdc', '\u6240\u6709', '\u7edd\u5bf9', '\u5df2\u7ecf\u6b7b\u4ea1',
        '\u98a0\u8986', '\u5fc5\u987b'
    ]
    for s in sentences:
        if any(trigger in s for trigger in triggers):
            if 8 <= len(s) <= 90:
                clash_points.append({
                    'claim': s,
                    'context': f'\u539f\u6587\u7b2c {len(clash_points) + 1} \u5904\u5173\u952e\u65ad\u8a00',
                    'suggested_critique_angle': '\u5ba1\u89c6\u8be5\u65ad\u8a00\u662f\u5426\u8fc7\u4e8e\u7edd\u5bf9\uff1f\u5728\u8fb9\u754c\u573a\u666f\u6216\u6781\u7aef\u7ea6\u675f\u4e0b\u662f\u5426\u4f9d\u7136\u6210\u7acb\uff1f',
                })
            if len(clash_points) >= 4:
                break

    if not clash_points and sentences:
        for s in sentences[:3]:
            clash_points.append({
                'claim': s,
                'context': '\u4f5c\u8005\u7684\u6838\u5fc3\u8bba\u65ad\u4e4b\u4e00',
                'suggested_critique_angle': '\u4f60\u5bf9\u8be5\u8bba\u70b9\u7684\u771f\u5b9e\u770b\u6cd5\u4e0e\u4eb2\u8eab\u4f53\u9a8c\u662f\u5426\u4e00\u81f4\uff1f',
            })

    blueprint = {
        'hook_style': f'\u4ee5\u201c{hook[:40]}...\u201d\u5feb\u901f\u52fe\u8d77\u9605\u8bfb\u5174\u8da3',
        'structural_stages': stages,
        'emotional_arc': emotional_arc,
        'pacing': pacing,
        'word_count': total_len,
    }

    return {
        'blueprint': blueprint,
        'clash_points': clash_points,
        'analysis_type': 'benchmark',
    }


def mine_dialogue(content):
    sentences = extract_sentences(content)
    user_stances = []
    triggers = ['\u6211\u8ba4\u4e3a', '\u6211\u89c9\u5f97', '\u6211\u7684\u770b\u6cd5', '\u4e0d\u540c\u610f', '\u53cd\u9a73', '\u5173\u952e\u662f', '\u6070\u6070\u76f8\u53cd']
    for s in sentences:
        if any(k in s for k in triggers):
            user_stances.append(s)

    if not user_stances:
        user_stances = sentences[:3]

    return {
        'user_stances': user_stances,
        'viewpoint_insights': [
            f'\u5173\u4e8e\u300c{s[:18]}...\u300d\u7684\u9c9c\u660e\u4e3b\u5f20' for s in user_stances[:3]
        ],
        'analysis_type': 'dialogue',
    }


def main():
    parser = argparse.ArgumentParser(description='Mine viewpoints, blueprints, and DNA insights.')
    parser.add_argument('--content', help='Text content to analyze')
    parser.add_argument('--analysis_type', default='own_work', choices=['own_work', 'benchmark', 'dialogue'])
    parser.add_argument('--json', help='JSON payload')
    parser.add_argument('--file', help='Path to JSON file with input parameters')
    args = parser.parse_args()

    content = args.content or ''
    analysis_type = args.analysis_type

    if args.file and Path(args.file).exists():
        try:
            p = json.loads(Path(args.file).read_text(encoding='utf-8'))
            content = p.get('content', content)
            analysis_type = p.get('analysis_type', analysis_type)
        except Exception:
            pass

    if args.json:
        try:
            p = json.loads(args.json)
            content = p.get('content', content)
            analysis_type = p.get('analysis_type', analysis_type)
        except Exception:
            pass

    if not content and not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read().strip()
            if stdin_data:
                try:
                    p = json.loads(stdin_data)
                    content = p.get('content', content)
                    analysis_type = p.get('analysis_type', analysis_type)
                except Exception:
                    content = stdin_data
        except Exception:
            pass

    if not content:
        print(json.dumps({'error': 'No content provided for analysis.'}, ensure_ascii=False))
        sys.exit(1)

    if analysis_type == 'benchmark':
        result = mine_benchmark(content)
    elif analysis_type == 'dialogue':
        result = mine_dialogue(content)
    else:
        result = mine_own_work(content)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
