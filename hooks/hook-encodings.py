hiddenimports = [
    'encodings.utf_8',
    'encodings.ascii',
    'encodings.latin_1',
    'encodings.utf_16',
    'encodings.utf_32'
]

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('requests')

excludedimports = [
    'requests.packages.urllib3.contrib.pyopenssl',
    'requests.packages.urllib3.contrib.securetransport'
]