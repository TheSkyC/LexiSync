from contextlib import contextmanager
import logging
import os

logger = logging.getLogger(__name__)


def atomic_write_text(content: str, target_path: str, encoding: str = "utf-8"):
    """
    Atomically writes string content to a file.

    Writes to a temporary file first, then renames it to the target path.
    This prevents data corruption if the write operation is interrupted.

    :param content: The string content to write.
    :param target_path: The final destination file path.
    :param encoding: The file encoding to use.
    :return: True on success, False on failure.
    """
    temp_path = target_path + ".tmp"
    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        with open(temp_path, "w", encoding=encoding, newline="") as f:
            f.write(content)

        os.replace(temp_path, target_path)
        return True
    except OSError as e:
        logger.error(f"Failed to atomically write to {target_path}: {e}")
        return False
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError as e:
                logger.error(f"Failed to remove temporary file {temp_path}: {e}")


@contextmanager
def atomic_open(filepath, mode="w", encoding="utf-8", **kwargs):
    """
    一个通用的原子写入上下文管理器。
    用法与内置的 open() 完全相同，支持文本('w')和二进制('wb')模式。

    示例:
        with atomic_open('data.json', 'w') as f:
            json.dump(data, f)

        with atomic_open('data.xml', 'wb') as f:
            tree.write(f)
    """
    if "r" in mode or "a" in mode:
        raise ValueError("atomic_open only supports write modes ('w', 'wb').")

    temp_filepath = filepath + ".tmp"
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    open_kwargs = kwargs.copy()
    if "b" not in mode:
        open_kwargs["encoding"] = encoding

    f = None
    try:
        with open(temp_filepath, mode, **open_kwargs) as f:
            yield f
        os.replace(temp_filepath, filepath)

    except Exception:
        if f:
            f.close()
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except OSError:
                pass
        raise
