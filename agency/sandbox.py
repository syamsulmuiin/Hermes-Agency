"""Fail-closed Linux bubblewrap capability probe; no agent command execution.

This module executes only a fixed, harmless /bin/true inside a namespace.
It does not establish production-grade resource isolation or tool-side fencing.
"""
import os
import stat
import resource
import shutil
import subprocess
import sys

def _limits():
    # Applied to bwrap and inherited by its child. Not a cgroup or a guarantee
    # against all resource exhaustion; the subprocess timeout is independent.
    resource.setrlimit(resource.RLIMIT_CPU,(2,2))
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
    resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))

def sandbox_probe(timeout=5):
    if sys.platform!='linux' or os.name!='posix':
        raise RuntimeError('Sandbox probe requires Linux')
    if type(timeout) not in (int,float) or not 1<=timeout<=10:
        raise ValueError('Invalid timeout')
    binary=shutil.which('bwrap')
    if binary is None or not os.path.isabs(binary):
        raise RuntimeError('bubblewrap not installed')
    # /bin is a symlink to /usr/bin on merged-/usr systems. Bind /usr only,
    # then recreate /bin as a symlink inside the isolated root.
    if not os.path.isfile('/usr/bin/true') or not os.access('/usr/bin/true',os.X_OK):
        raise RuntimeError('Required system executable missing')
    if os.path.islink('/bin') and os.readlink('/bin') != 'usr/bin':
        raise RuntimeError('Unsupported /bin symlink layout')
    if not os.path.islink('/bin'):
        raise RuntimeError('Sandbox probe requires merged-/usr layout')
    argv=[binary,'--die-with-parent','--new-session','--unshare-all',
          '--clearenv','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin',
          '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
          '--','/bin/true']
    try:
        result=subprocess.run(argv,stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                              timeout=timeout,check=False,env={},preexec_fn=_limits)
    except (subprocess.TimeoutExpired,OSError,ValueError) as exc:
        raise RuntimeError('Sandbox probe failed') from exc
    if result.returncode!=0:
        detail=result.stderr.decode('utf-8','replace')[:1200].strip()
        raise RuntimeError('Sandbox unavailable or isolation denied (exit '+str(result.returncode)+'): '+(detail or 'no stderr'))
    return {'isolated_probe':True,'agent_tools_enabled':False,
            'resource_limits':'rlimit-probe-only'}
