"""Supervise a loopback-only core and public, authenticated Next.js frontend."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from urllib.request import urlopen


def main():
    token=os.getenv('SHY_ACCESS_TOKEN','')
    password=os.getenv('SHY_OWNER_PASSWORD','')
    origin=os.getenv('SHY_PUBLIC_ORIGIN') or os.getenv('RENDER_EXTERNAL_URL')
    if len(token)<32 or len(password)<8 or not os.getenv('SHY_OWNER_USERNAME') or not origin or not os.getenv('DATABASE_URL'):
        raise RuntimeError('Hosted SHY requires owner credentials, origin and a PostgreSQL connection.')
    port=int(os.getenv('PORT','10000'))
    if not 1024 <= port <= 65535 or port==8000:raise RuntimeError('Invalid frontend port')
    app_root=Path(__file__).resolve().parent
    env={**os.environ,'SHY_REQUIRE_AUTH':'1','SHY_BACKEND_BASE_URL':'http://127.0.0.1:8000','SHY_PUBLIC_ORIGIN':origin}
    children=[];stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
        for child in children:
            if child.poll() is None:child.terminate()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        core=subprocess.Popen([sys.executable,'-m','uvicorn','main:app','--host','127.0.0.1','--port','8000'],cwd=app_root,env=env)
        children.append(core)
        ready=False
        for _ in range(450):
            if stopping or core.poll() is not None:break
            try:
                with urlopen('http://127.0.0.1:8000/livez',timeout=1) as response:
                    ready=response.status==200
                if ready:break
            except OSError:pass
            time.sleep(.2)
        if stopping:return 0
        if not ready:raise RuntimeError('Core failed to become ready; frontend was not exposed.')
        web=subprocess.Popen(['node','node_modules/next/dist/bin/next','start','--hostname','0.0.0.0','--port',str(port)],cwd=app_root/'web',env=env)
        children.append(web)
        while not stopping and all(child.poll() is None for child in children):time.sleep(.2)
        return 0 if stopping else 1
    finally:
        stop()
        deadline=time.monotonic()+10
        for child in children:
            try:child.wait(timeout=max(.1,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:child.kill();child.wait()

if __name__=='__main__':sys.exit(main())
