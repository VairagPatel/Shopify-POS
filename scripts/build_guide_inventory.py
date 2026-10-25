"""Refresh the self-contained reading guide's inventories from repository sources."""
import ast
import html
import re
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# Replace a marked section so regeneration remains repeatable without duplicate rows.
def replace_section(document, label, content):
    start, end = f'<!-- {label} -->', f'<!-- END_{label} -->'
    if end in document:
        return re.sub(re.escape(start)+r'.*?'+re.escape(end),lambda _:start+content+end,document,flags=re.S)
    return document.replace(start,start+content+end)


# Embed escaped case, permission and test-function data without third-party assets.
def main():
    path=ROOT/'app/static/flow-guide.html'
    document=path.read_text(encoding='utf-8')
    plan=(ROOT/'docs/PRODUCTION_TEST_PLAN.md').read_text(encoding='utf-8')
    plan_rows=[]
    for line in plan.splitlines():
        if re.match(r'\| [A-Z]+-\d+',line):
            cells=[cell.strip() for cell in line.strip('|').split('|')]
            plan_rows.append('<tr data-search>'+''.join('<td>'+html.escape(cell)+'</td>' for cell in cells)+'</tr>')
    endpoints=runpy.run_path(str(ROOT/'tests/endpoint_matrix.py'))['ENDPOINTS']
    endpoint_rows=[]
    for method,url,_,roles,status,_ in endpoints:
        endpoint_rows.append('<tr data-search><td><code>'+html.escape(method+' '+url)+'</code></td><td>'+html.escape(', '.join(sorted(roles)))+'</td><td>'+str(status)+'</td></tr>')
    tests=[]
    for source in sorted((ROOT/'tests').glob('test_*.py')):
        for node in ast.parse(source.read_text(encoding='utf-8-sig')).body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                title=node.name.removeprefix('test_').replace('_',' ').capitalize()
                location=f'tests/{source.name}:{node.lineno}'
                description=ast.get_docstring(node) or title
                tests.append(f'<div class="card" data-search style="margin:10px 0"><h3>{html.escape(title)}</h3><p>{html.escape(description)}</p><div class="small test-name">{html.escape(location)}<br><code>{html.escape(node.name)}</code></div></div>')
    document=replace_section(document,'PLAN_ROWS','\n'.join(plan_rows))
    document=replace_section(document,'ENDPOINT_ROWS','\n'.join(endpoint_rows))
    document=replace_section(document,'AUTOMATED_TESTS','\n'.join(tests))
    path.write_text(document,encoding='utf-8')
    print(f'Guide refreshed: {len(plan_rows)} planned scenarios, {len(endpoint_rows)} endpoint actions, {len(tests)} test functions.')


if __name__=='__main__':
    main()
