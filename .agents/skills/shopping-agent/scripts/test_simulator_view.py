"""Run JS view/input-event unit tests without a browser; does NOT test dragging."""
import argparse
import os
import subprocess
import tempfile
from pathlib import Path
from simulator import demo_profile,build_payload,write_preview
from shopping import today

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node',default='node')
    args=parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        for name,product,price in [('nike-simulator.html','Nike Air Force 1','3200'),('headphones-simulator.html','หูฟังจำลอง','5500')]:
            write_preview(build_payload(demo_profile(today()),dict(productName=product,productPrice=price),today(),minimum=1000,maximum=12000,step=100),root/name)
        env={**os.environ,'SIMULATOR_PREVIEW_DIR':str(root)+os.sep}
        test_file=Path(__file__).resolve().parents[1]/'component_tests/test_simulator_dom.cjs'
        raise SystemExit(subprocess.run([args.node,'--test',str(test_file)],env=env).returncode)
