# pointer.py
# Git LFS pointer files
# Copyright (C) 2019 Andrej Shadura <andrew@shadura.me>
#
# This library is dual-licensed under the Apache License, Version 2.0 and the GNU
# General Public License as public by the Free Software Foundation; version 2.0
# or (at your option) any later version. You can redistribute it and/or
# modify it under the terms of either of these two licenses.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# You should have received a copy of the licenses; if not, see
# <http://www.gnu.org/licenses/> for a copy of the GNU General Public License
# and <http://www.apache.org/licenses/LICENSE-2.0> for a copy of the Apache
# License, Version 2.0.
#

"""Git LFS pointer files"""

from enum import Enum
from typing import Type, IO

import binascii
from io import BytesIO

class Key(object):
    VERSION = b'version'
    OID = b'oid'
    SIZE = b'size'

class Version(Enum):
    V1 = b'https://git-lfs.github.com/spec/v1'
    PRE = b'https://hawser.github.com/spec/v1'
    ALPHA = b'http://git-media.io/v/2'

    @classmethod
    def verify(cls: Type[Enum], line: str) -> bool:
        return line in [v.value for v in cls.__members__.values()]

class VersionUnsupportedException(Exception):
    """Indicated the pointer file version is not supported."""

class PointerFormatException(Exception):
    """Indicates an error parsing a pointer file."""

class SHA256(object):
    """SHA object that behaves like hashlib's but is given a fixed value."""

    __slots__ = ('_hexsha', '_sha')

    digest_size = 256 / 8
    digest_name = 'sha256'

    def __init__(self, hexsha):
        """
        >>> SHA256('4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393')
        <SHA256 4d7a214>
        >>> SHA256(b'4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393')
        <SHA256 4d7a214>
        >>> SHA256('4d7a214614ab2935c943f9e0ff69d22eadbb8f32')
        Traceback (most recent call last):
          ...
        ValueError: Expected 64 hex digits, got b'4d7a214614ab2935c943f9e0ff69d22eadbb8f32'
        """
        if getattr(hexsha, 'encode', None) is not None:
            hexsha = hexsha.encode('ascii')
        if not isinstance(hexsha, bytes):
            raise TypeError('Expected bytes for hexsha, got %r' % hexsha)
        if len(hexsha) != (256 / 4):
            raise ValueError('Expected %d hex digits, got %r' % (256 / 4, hexsha))
        self._hexsha = hexsha
        self._sha = binascii.unhexlify(hexsha)

    def digest(self):
        """Return the raw SHA digest."""
        return self._sha

    def hexdigest(self):
        """Return the hex SHA digest."""
        return self._hexsha.decode('ascii')

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.hexdigest()[0:7])

supported_digests = {b'sha256': SHA256}

class Pointer(object):
    __slots__ = ('_attrs', 'oid', 'size')

    version = Version.V1

    def __init__(self):
        self._attrs = dict()
        self.oid = None
        self.size = 0

    @staticmethod
    def _verify_version(line: bytes) -> bool:
        r"""Verify the version line against the list of supported versions

        >>> Pointer._verify_version(b'version https://git-lfs.github.com/spec/v1\n')
        True
        >>> Pointer._verify_version(b'version 1\n')
        False
        >>> Pointer._verify_version(b'Version 1\n')
        PointerFormatException('Missing version')
        """
        if line.endswith(b'\n') and b' ' in line:
            key, value = line.rstrip(b'\n').split(b' ', 1)
            if key == Key.VERSION:
                return Version.verify(value)
        return PointerFormatException('Missing version')

    @classmethod
    def from_file(cls, f: IO[bytes]):
        """Create a pointer file from a file-like object."""
        line = f.readline(256)
        if not line:
            return cls()
        if not cls._verify_version(line):
            raise VersionUnsupportedException('Invalid version')
        attrs = dict()
        for line in f:
            key, value = line.rstrip(b'\n').split(b' ', 1)
            attrs[key] = value
        oid_type, oid_hash = attrs[Key.OID].split(b':', 1)
        if oid_type not in supported_digests:
            raise PointerFormatException('Unsupported oid type %s' % oid_type)
        oid = supported_digests[oid_type](oid_hash)
        if not attrs[Key.SIZE].isdigit():
            raise PointerFormatException('Expected integer size, got %s' % attrs[Key.SIZE])
        size = int(attrs[Key.SIZE])
        obj = cls()
        obj._attrs = attrs
        obj.oid = oid
        obj.size = size
        return obj

    @classmethod
    def from_path(cls, path: bytes):
        """Open a pointer file from disk."""
        with open(path, 'rb') as f:
            return cls.from_file(f)

    @classmethod
    def from_bytes(cls, b: bytes):
        """Create a pointer file from a byte string.

        >>> Pointer.from_bytes(b'''version https://git-lfs.github.com/spec/v1
        ... oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393
        ... size 12345
        ... ''')
        <Pointer V1 4d7a214 (size 12345)>
        >>> Pointer.from_bytes(b'')
        <Pointer V1 (size 0)>
        """
        with BytesIO(b) as f:
            return cls.from_file(f)

    def __bytes__(self):
        r"""Generate byte representation of the pointer file object

        >>> bytes(Pointer.from_bytes(b'''version https://git-lfs.github.com/spec/v1
        ... oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393
        ... size 12345
        ... '''))
        b'version https://git-lfs.github.com/spec/v1\noid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393\nsize 12345\n'
        >>> bytes(Pointer.from_bytes(b'''version https://hawser.github.com/spec/v1
        ... size 12345
        ... oid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393
        ... '''))
        b'version https://git-lfs.github.com/spec/v1\noid sha256:4d7a214614ab2935c943f9e0ff69d22eadbb8f32b1258daaa5e2ca24d17e2393\nsize 12345\n'
        """
        self._attrs[Key.SIZE] = b'%d' % self.size
        self._attrs[Key.OID] = ('%s:%s' % (self.oid.digest_name, self.oid.hexdigest())).encode('ascii')
        attrs = [(Key.VERSION, self.version.value)] + sorted(self._attrs.items())
        return b'\n'.join([b' '.join(kv) for kv in attrs]) + b'\n'

    def __repr__(self):
        if self.size:
            return "<%s %s %s (size %s)>" % (self.__class__.__name__, self.version.name, self.oid.hexdigest()[0:7], self.size)
        else:
            return "<%s %s (size %s)>" % (self.__class__.__name__, self.version.name, self.size)

if __name__ == '__main__':
    import doctest
    doctest.testmod()
