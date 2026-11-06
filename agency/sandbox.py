"""Linux bubblewrap smoke-test sandbox; not an agent tool executor.

Only a fixed /bin/true probe is permitted. No user-controlled command,
filesystem bind, network destination, or arbitrary tool parameters.
"""
import os
import shutil
import subprocess
import sys

def sandbox_probe(timeout=5):
    if sys.platform!='linux' or os.name!='posix':
        raise RuntimeError('Sandbox probe requires Linux')
    if type(timeout) not in (int,float) or not 1<=timeout<=10:
        raise ValueError('Invalid timeout')
    binary=shutil.which('bwrap')
    if binary is None or not os.path.isabs(binary):
        raise RuntimeError('bubblewrap not installed')
    # Explicitly no network, no inherited writable host filesystem,
    # and no user-selected executable. This is a capability probe only.
    argv=[binary,'--die-with-parent','--new-session',
          '--unshare-all','--clearenv','--ro-bind','/bin','/bin',
          '--ro-bind','/usr','/usr','--proc','/proc','--dev','/dev',
          '--tmpfs','/tmp','--','/bin/true']
    try:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              timeout=timeout,check=False,env={})
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('Sandbox probe timed out') from exc
    if result.returncode!=0:
        raise RuntimeError('Sandbox unavailable or isolation denied')
    return {'isolated_probe':True,'agent_tools_enabled':False}
