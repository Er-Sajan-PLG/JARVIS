import os, subprocess, sys
for pkg in sys.argv[1:]:
    mod = pkg.replace('-', '_').replace('.', '_').lower()
    result = subprocess.run(['grep', '-rn', f'import {mod}|from {mod}', '/home/sajan/Projects/JARVIS/app/', '--include=*.py'], capture_output=True, text=True)
    if not result.stdout.strip():
        print(f'UNUSED: {pkg}')
