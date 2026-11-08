"""Descriptor-relative snapshot inventory traversal; no service execution."""
import os
import stat


_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def inventory(root):
    """Return (files with bytes and modes, directories), fail closed on links."""
    fd = os.open(root, _FLAGS)
    files, directories = {}, set()
    try:
        def walk(directory_fd, prefix):
            info = os.fstat(directory_fd)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                raise PermissionError("Untrusted snapshot directory")
            for name in os.listdir(directory_fd):
                if name in (".", "..") or "/" in name or "\x00" in name:
                    raise PermissionError("Unsafe snapshot entry")
                relative = prefix + name
                entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if entry.st_uid != 0 or entry.st_mode & 0o022:
                    raise PermissionError("Untrusted snapshot entry")
                if stat.S_ISDIR(entry.st_mode):
                    child = os.open(name, _FLAGS, dir_fd=directory_fd)
                    try:
                        opened = os.fstat(child)
                        if (opened.st_dev, opened.st_ino) != (entry.st_dev, entry.st_ino):
                            raise PermissionError("Snapshot directory replaced")
                        directories.add(relative)
                        walk(child, relative + "/")
                    finally:
                        os.close(child)
                elif stat.S_ISREG(entry.st_mode) and entry.st_nlink == 1:
                    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
                    child = os.open(name, flags, dir_fd=directory_fd)
                    try:
                        opened = os.fstat(child)
                        if ((opened.st_dev, opened.st_ino) != (entry.st_dev, entry.st_ino)
                                or not stat.S_ISREG(opened.st_mode)
                                or opened.st_nlink != 1
                                or opened.st_uid != 0
                                or opened.st_mode & 0o022):
                            raise PermissionError("Snapshot file replaced")
                        chunks = []
                        while True:
                            part = os.read(child, 1024 * 1024)
                            if not part:
                                break
                            chunks.append(part)
                        after = os.fstat(child)
                        if (after.st_size != opened.st_size or
                                after.st_mtime_ns != opened.st_mtime_ns or
                                after.st_ctime_ns != opened.st_ctime_ns):
                            raise PermissionError("Snapshot changed during read")
                        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                            raise PermissionError("Snapshot file path replaced")
                        files[relative] = (stat.S_IMODE(opened.st_mode), b"".join(chunks))
                    finally:
                        os.close(child)
                else:
                    raise PermissionError("Unsupported snapshot entry")
        walk(fd, "")
        return files, directories
    finally:
        os.close(fd)
