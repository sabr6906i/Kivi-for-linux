import importlib.util
import io
from pathlib import Path
import tarfile
import unittest

spec=importlib.util.spec_from_file_location('build_deb',Path(__file__).resolve().parents[1]/'scripts/build-deb.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class DebianArchiveTests(unittest.TestCase):
    def test_parent_directories_precede_files_for_dpkg_unpack(self):
        payload={'usr/lib/bol-linux/bol.py':(b'print("Bol")',0o644),
                 'usr/share/applications/bol.desktop':(b'entry',0o644)}
        raw=builder.tar_gz(payload,1000)
        seen=set()
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
            for member in archive.getmembers():
                name=member.name.removeprefix('./').rstrip('/')
                if member.isdir():seen.add(name)
                else:
                    self.assertIn(str(Path(name).parent),seen)
                    self.assertEqual(member.uid,0)
                    self.assertEqual(member.mode,0o644)
        self.assertIn('usr/lib/bol-linux',seen)
        self.assertEqual(raw,builder.tar_gz(payload,1000))
