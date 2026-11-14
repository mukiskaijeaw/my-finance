"""Local STDIO MCP demo only. No sockets, database, private profiles or telemetry.

Prepared but NOT registered in the live desktop: enable_mcp_apps is false.
Protocol tests do not prove that Codex renders or clicks the widget.
"""
import json
import sys
from pathlib import Path
from simulator import demo_profile,build_payload,render_html
from shopping import today

BUTTON='ui://shopping/button-poc.html'
SIMULATOR='ui://shopping/simulator.html'
MIME='text/html;profile=mcp-app'
clicks=0


def tool(name,title,uri=None):
    data=dict(name=name,title=title,description=title+' — synthetic UI test only',
              inputSchema={'type':'object','properties':{},'additionalProperties':False},
              annotations={'readOnlyHint':name!='shopping_demo_click','destructiveHint':False,'openWorldHint':False})
    if uri:data['_meta']={'ui':{'resourceUri':uri},'openai/outputTemplate':uri}
    return data


def dispatch(method,params):
    global clicks
    if method=='initialize':
        return dict(protocolVersion=params.get('protocolVersion','2025-06-18'),
                    serverInfo={'name':'shopping-ui-poc','version':'0.1.0'},capabilities={'tools':{},'resources':{}},
                    instructions='Synthetic local UI test only. Never read, send or accept private financial data. No purchases or transactions.')
    if method=='ping':return {}
    if method=='tools/list':
        return {'tools':[tool('shopping_render_button_poc','Render one demo button',BUTTON),
                         tool('shopping_demo_click','Count synthetic button clicks'),
                         tool('shopping_render_simulator','Render synthetic purchase simulator',SIMULATOR)]}
    if method=='resources/list':
        return {'resources':[{'uri':u,'name':n,'mimeType':MIME} for u,n in ((BUTTON,'Synthetic button POC'),(SIMULATOR,'Synthetic simulator'))]}
    if method=='resources/read':
        uri=params.get('uri')
        if uri==BUTTON:text=(Path(__file__).resolve().parents[1]/'assets/mcp-button-poc.html').read_text(encoding='utf-8')
        elif uri==SIMULATOR:
            fixture=json.loads((Path(__file__).resolve().parents[1]/'tests/fixtures/simulator.json').read_text(encoding='utf-8'))
            text=render_html(build_payload(demo_profile(today()),fixture['product'],today(),**fixture['slider']))
        else:raise ValueError('unknown resource; arbitrary file reads forbidden')
        return {'contents':[{'uri':uri,'mimeType':MIME,'text':text,'_meta':{'ui':{'prefersBorder':True}}}]}
    if method=='tools/call':
        if params.get('arguments') not in ({},None):raise ValueError('demo tools accept no financial or other arguments')
        name=params.get('name')
        if name=='shopping_demo_click':clicks+=1
        elif name not in ('shopping_render_button_poc','shopping_render_simulator'):raise ValueError('unknown demo tool')
        return {'content':[{'type':'text','text':'Synthetic local UI test; no financial data loaded.'}],
                'structuredContent':{'demoMode':True,'clicks':clicks,'context':'synthetic-context-only'}}
    if method.startswith('notifications/'):return None
    raise ValueError('unknown method')


def main():
    for line in sys.stdin:
        ident=None
        try:
            if len(line)>100000:raise ValueError('request too large')
            request=json.loads(line)
            ident=request.get('id')
            result=dispatch(request['method'],request.get('params',{}))
            if ident is None:continue
            response={'jsonrpc':'2.0','id':ident,'result':result}
        except (ValueError,KeyError,TypeError,AttributeError) as error:
            if ident is None:continue
            response={'jsonrpc':'2.0','id':ident,'error':{'code':-32602,'message':str(error)}}
        print(json.dumps(response,ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdin.reconfigure(encoding='utf-8');sys.stdout.reconfigure(encoding='utf-8')
    main()
