from __future__ import print_function

import os, re, sys, time, json
from functools import partial

# Python 2 backwards compatibility
from future.utils import PY2
if PY2:
    from builtins import int

from bs4 import BeautifulSoup

from twisted.internet import reactor
from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks
from twisted.application import service

from allmydata import client, uri
from allmydata.introducer.server import create_introducer
from allmydata.storage.mutable import MutableShareFile
from allmydata.storage.server import si_a2b
from allmydata.immutable import offloaded, upload
from allmydata.immutable.literal import LiteralFileNode
from allmydata.immutable.filenode import ImmutableFileNode
from allmydata.util import idlib, mathutil, pollmixin, fileutil
from allmydata.util import log, base32
from allmydata.util.encodingutil import quote_output, unicode_to_argv
from allmydata.util.fileutil import abspath_expanduser_unicode
from allmydata.util.consumer import MemoryConsumer, download_to_data
from allmydata.stats import StatsGathererService
from allmydata.interfaces import IDirectoryNode, IFileNode, \
     NoSuchChildError, NoSharesError
from allmydata.monitor import Monitor
from allmydata.mutable.common import NotWriteableError
from allmydata.mutable import layout as mutable_layout
from allmydata.mutable.publish import MutableData

from foolscap.api import DeadReferenceError, fireEventually, flushEventualQueue
from twisted.python.failure import Failure

from .common import (
    TEST_RSA_KEY_SIZE,
    SameProcessStreamEndpointAssigner,
)
from .common_web import do_http, Error
from .web.common import (
    assert_soup_has_tag_with_attributes
)

# TODO: move this to common or common_util
from allmydata.test.test_runner import RunBinTahoeMixin
from . import common_util as testutil
from .common_util import run_cli

LARGE_DATA = """
This is some data to publish to the remote grid.., which needs to be large
enough to not fit inside a LIT uri.
"""

# our system test uses the same Tub certificates each time, to avoid the
# overhead of key generation
SYSTEM_TEST_CERTS = [
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNDAzM1oXDTIxMDEwMTAxNDAzM1owFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1iNV
z07PYwZwucl87QlL2TFZvDxD4flZ/p3BZE3DCT5Efn9w2NT4sHXL1e+R/qsDFuNG
bw1y1TRM0DGK6Wr0XRT2mLQULNgB8y/HrhcSdONsYRyWdj+LimyECKjwh0iSkApv
Yj/7IOuq6dOoh67YXPdf75OHLShm4+8q8fuwhBL+nuuO4NhZDJKupYHcnuCkcF88
LN77HKrrgbpyVmeghUkwJMLeJCewvYVlambgWRiuGGexFgAm6laS3rWetOcdm9eg
FoA9PKNN6xvPatbj99MPoLpBbzsI64M0yT/wTSw1pj/Nom3rwfMa2OH8Kk7c8R/r
U3xj4ZY1DTlGERvejQIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQAwyQjQ3ZgtJ3JW
r3/EPdqSUBamTfXIpOh9rXmRjPpbe+MvenqIzl4q+GnkL5mdEb1e1hdKQZgFQ5Q5
tbcNIz6h5C07KaNtbqhZCx5c/RUEH87VeXuAuOqZHbZWJ18q0tnk+YgWER2TOkgE
RI2AslcsJBt88UUOjHX6/7J3KjPFaAjW1QV3TTsHxk14aYDYJwPdz+ijchgbOPQ0
i+ilhzcB+qQnOC1s4xQSFo+zblTO7EgqM9KpupYfOVFh46P1Mak2W8EDvhz0livl
OROXJ6nR/13lmQdfVX6T45d+ITBwtmW2nGAh3oI3JlArGKHaW+7qnuHR72q9FSES
cEYA/wmk
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDWI1XPTs9jBnC5
yXztCUvZMVm8PEPh+Vn+ncFkTcMJPkR+f3DY1PiwdcvV75H+qwMW40ZvDXLVNEzQ
MYrpavRdFPaYtBQs2AHzL8euFxJ042xhHJZ2P4uKbIQIqPCHSJKQCm9iP/sg66rp
06iHrthc91/vk4ctKGbj7yrx+7CEEv6e647g2FkMkq6lgdye4KRwXzws3vscquuB
unJWZ6CFSTAkwt4kJ7C9hWVqZuBZGK4YZ7EWACbqVpLetZ605x2b16AWgD08o03r
G89q1uP30w+gukFvOwjrgzTJP/BNLDWmP82ibevB8xrY4fwqTtzxH+tTfGPhljUN
OUYRG96NAgMBAAECggEAJ5xztBx0+nFnisZ9yG8uy6d4XPyc5gE1J4dRDdfgmyYc
j3XNjx6ePi4cHZ/qVryVnrc+AS7wrgW1q9FuS81QFKPbFdZB4SW3/p85BbgY3uxu
0Ovz3T3V9y4polx12eCP0/tKLVd+gdF2VTik9Sxfs5rC8VNN7wmJNuK4A/k15sgy
BIu/R8NlMNGQySNhtccp+dzB8uTyKx5zFZhVvnAK/3YX9BC2V4QBW9JxO4S8N0/9
48e9Sw/fGCfQ/EFPKGCvTvfuRqJ+4t5k10FygXJ+s+y70ifYi+aSsjJBuranbLJp
g5TwhuKnTWs8Nth3YRLbcJL4VBIOehjAWy8pDMMtlQKBgQD0O8cHb8cOTGW0BijC
NDofhA2GooQUUR3WL324PXWZq0DXuBDQhJVBKWO3AYonivhhd/qWO8lea9MEmU41
nKZ7maS4B8AJLJC08P8GL1uCIE/ezEXEi9JwC1zJiyl595Ap4lSAozH0DwjNvmGL
5mIdYg0BliqFXbloNJkNlb7INwKBgQDgdGEIWXc5Y1ncWNs6iDIV/t2MlL8vLrP0
hpkl/QiMndOQyD6JBo0+ZqvOQTSS4NTSxBROjPxvFbEJ3eH8Pmn8gHOf46fzP1OJ
wlYv0gYzkN4FE/tN6JnO2u9pN0euyyZLM1fnEcrMWColMN8JlWjtA7Gbxm8lkfa4
3vicaJtlWwKBgQCQYL4ZgVR0+Wit8W4qz+EEPHYafvwBXqp6sXxqa7qXawtb+q3F
9nqdGLCfwMNA+QA37ksugI1byfXmpBH902r/aiZbvAkj4zpwHH9F0r0PwbY1iSA9
PkLahX0Gj8OnHFgWynsVyGOBWVnk9oSHxVt+7zWtGG5uhKdUGLPZugocJQKBgB61
7bzduOFiRZ5PjhdxISE/UQL2Kz6Cbl7rt7Kp72yF/7eUnnHTMqoyFBnRdCcQmi4I
ZBrnUXbFigamlFAWHhxNWwSqeoVeychUjcRXQT/291nMhRsA02KpNA66YJV6+E9b
xBA6r/vLqGCUUkAWcFfVpIyC1xxV32MmJvAHpBN3AoGAPF3MUFiO0iKNZfst6Tm3
rzrldLawDo98DRZ7Yb2kWlWZYqUk/Nvryvo2cns75WGSMDYVbbRp+BY7kZmNYa9K
iQzKDL54ZRu6V+getJdeAO8yXoCmnZKxt5OHvOSrQMfAmFKSwLwxBbZBfXEyuune
yfusXLtCgajpreoVIa0xWdQ=
-----END PRIVATE KEY-----
""", # 0
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNDAzM1oXDTIxMDEwMTAxNDAzM1owFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEApDzW
4ZBeK9w4xpRaed6lXzeCO0Xmr3f0ynbueSdiZ89FWoAMgK+SiBIOViYV6hfm0Wah
lemSNzFGx5LvDSg2uwSqEP23DeM9O/SQPgIAiLeeEsYZJcgg2jz92YfFEaahsGdI
6qSP4XI2/5dgKRpPOYDGyw6R5PQR6w22Xq1WD1jBvImk/k09I9jHRn40pYbaJzbg
U2aIjvOruo2kqe4f6iDqE0piYimAZJUvemu1UoyV5NG590hGkDuWsMD77+d2FxCj
9Nzb+iuuG3ksnanHPyXi1hQmzp5OmzVWaevCHinNjWgsuSuLGO9H2SLf3wwp2UCs
EpKtzoKrnZdEg/anNwIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQChxtr67o1aZZMJ
A6gESPtFjZLw6wG0j50JsrWKLvoXVts1ToJ9u2nx01aFKjBwb4Yg+vdJfDgIIAEm
jS56h6H2DfJlkTWHmi8Vx1wuusWnrNwYMI53tdlRIpD2+Ne7yeoLQZcVN2wuPmxD
Mbksg4AI4csmbkU/NPX5DtMy4EzM/pFvIcxNIVRUMVTFzn5zxhKfhyPqrMI4fxw1
UhUbEKO+QgIqTNp/dZ0lTbFs5HJQn6yirWyyvQKBPmaaK+pKd0RST/T38OU2oJ/J
LojRs7ugCJ+bxJqegmQrdcVqZZGbpYeK4O/5eIn8KOlgh0nUza1MyjJJemgBBWf7
HoXB8Fge
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQCkPNbhkF4r3DjG
lFp53qVfN4I7Reavd/TKdu55J2Jnz0VagAyAr5KIEg5WJhXqF+bRZqGV6ZI3MUbH
ku8NKDa7BKoQ/bcN4z079JA+AgCIt54SxhklyCDaPP3Zh8URpqGwZ0jqpI/hcjb/
l2ApGk85gMbLDpHk9BHrDbZerVYPWMG8iaT+TT0j2MdGfjSlhtonNuBTZoiO86u6
jaSp7h/qIOoTSmJiKYBklS96a7VSjJXk0bn3SEaQO5awwPvv53YXEKP03Nv6K64b
eSydqcc/JeLWFCbOnk6bNVZp68IeKc2NaCy5K4sY70fZIt/fDCnZQKwSkq3Ogqud
l0SD9qc3AgMBAAECggEBAIu55uaIOFYASZ1IYaEFNpRHWVisI5Js76nAfSo9w46l
3E8eWYSx2mxBUEkipco/A3RraFVuHaMvHRR1gUMkT0vUsAs8jxwVk+cKLh1S/rlR
3f4C4yotlSWWdjE3PQXDShQWCwb1ciNPVFMmqfzOEVDOqlHe12h97TCYverWdT0f
3LZICLQsZd1WPKnPNXrsRRDCBuRLapdg+M0oJ+y6IiCdm+qM7Qvaoef6hlvm5ECz
LCM92db5BKTuPOQXMx2J8mjaBgU3aHxRV08IFgs7mI6q0t0FM7LlytIAJq1Hg5QU
36zDKo8tblkPijWZWlqlZCnlarrd3Ar/BiLEiuOGDMECgYEA1GOp0KHy0mbJeN13
+TDsgP7zhmqFcuJREu2xziNJPK2S06NfGYE8vuVqBGzBroLTQ3dK7rOJs9C6IjCE
mH7ZeHzfcKohpZnl443vHMSpgdh/bXTEO1aQZNbJ2hLYs8ie/VqqHR0u6YtpUqZL
LgaUA0U8GnlsO55B8kyCelckmDkCgYEAxfYQMPEEzg1tg2neqEfyoeY0qQTEJTeh
CPMztowSJpIyF1rQH6TaG0ZchkiAkw3W58RVDfvK72TuVlC5Kz00C2/uPnrqm0dX
iMPeML5rFlG3VGCrSTnAPI+az6P65q8zodqcTtA8xoxgPOlc/lINOxiTEMxLyeGF
8GyP+sCM2u8CgYEAvMBR05OJnEky9hJEpBZBqSZrQGL8dCwDh0HtCdi8JovPd/yx
8JW1aaWywXnx6uhjXoru8hJm54IxWV8rB+d716OKY7MfMfACqWejQDratgW0wY7L
MjztGGD2hLLJGYXLHjfsBPHBllaKZKRbHe1Er19hWdndQWKVEwPB1X4KjKkCgYEA
nWHmN3K2djbYtRyLR1CEBtDlVuaSJmCWp23q1BuCJqYeKtEpG69NM1f6IUws5Dyh
eXtuf4KKMU8V6QueW1D6OomPaJ8CO9c5MWM/F5ObwY/P58Y/ByVhvwQQeToONC5g
JzKNCF+nodZigKqrIwoKuMvtx/IT4vloKd+1jA5fLYMCgYBoT3HLCyATVdDSt1TZ
SbEDoLSYt23KRjQV93+INP949dYCagtgh/kTzxBopw5FljISLfdYizIRo2AzhhfP
WWpILlnt19kD+sNirJVqxJacfEZsu5baWTedI/yrCuVsAs/s3/EEY6q0Qywknxtp
Fwh1/8y5t14ib5fxOVhi8X1nEA==
-----END PRIVATE KEY-----
""", # 1
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNDAzM1oXDTIxMDEwMTAxNDAzM1owFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwMTn
hXnpKHGAir3WYbOxefVrMA07OZNAsNa29nBwLA+NVIJNUFgquibMj7QYo8+M45oY
6LKr4yRcBryZVvyxfdr92xp8+kLeVApk2WLjkdBTRagHh9qdrY0hQmagCBN6/hLG
Xug8VksQUdhX3vu6ZyMvTLfKRkDOMRVkRGRGg/dOcvom7zpqMCGYenMG2FStr6UV
3s3dlCSZZTdTX5Uoq6yfUUJE3nITGKjpnpJKqIs3PWCIxdj7INIcjJKvIdUcavIV
2hEhh60A8ltmtdpQAXVBE+U7aZgS1fGAWS2A0a3UwuP2pkQp6OyKCUVHpZatbl9F
ahDN2QBzegv/rdJ1zwIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQAl4OQZ+FB9ZSUv
FL/KwLNt+ONU8Sve/xiX+8vKAvgKm2FrjyK+AZPwibnu+FSt2G4ndZBx4Wvpe5V+
gCsbzSXlh9cDn2SRXyprt2l/8Fj4eUMaThmLKOK200/N/s2SpmBtnuflBrhNaJpw
DEi2KEPuXsgvkuVzXN06j75cUHwn5LeWDAh0RalkVuGbEWBoFx9Hq8WECdlCy0YS
y09+yO01qz70y88C2rPThKw8kP4bX8aFZbvsnRHsLu/8nEQNlrELcfBarPVHjJ/9
imxOdymJkV152V58voiXP/PwXhynctQbF7e+0UZ+XEGdbAbZA0BMl7z+b09Z+jF2
afm4mVox
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDAxOeFeekocYCK
vdZhs7F59WswDTs5k0Cw1rb2cHAsD41Ugk1QWCq6JsyPtBijz4zjmhjosqvjJFwG
vJlW/LF92v3bGnz6Qt5UCmTZYuOR0FNFqAeH2p2tjSFCZqAIE3r+EsZe6DxWSxBR
2Ffe+7pnIy9Mt8pGQM4xFWREZEaD905y+ibvOmowIZh6cwbYVK2vpRXezd2UJJll
N1NflSirrJ9RQkTechMYqOmekkqoizc9YIjF2Psg0hyMkq8h1Rxq8hXaESGHrQDy
W2a12lABdUET5TtpmBLV8YBZLYDRrdTC4/amRCno7IoJRUellq1uX0VqEM3ZAHN6
C/+t0nXPAgMBAAECggEAF+2ZK4lZdsq4AQDVhqUuh4v+NSW/T0NHCWxto6OLWPzJ
N09BV5LKIvdD9yaM1HCj9XCgXOooyfYuciuhARo20f+H+VWNY+c+/8GWiSFsTCJG
4+Oao7NwVSWqljp07Ou2Hamo9AjxzGhe6znmlmg62CiW63f45MWQkqksHA0yb5jg
/onJ2//I+OI+aTKNfjt1G6h2x7oxeGTU1jJ0Hb2xSh+Mpqx9NDfb/KZyOndhSG5N
xRVosQ6uV+9mqHxTTwTZurTG31uhZzarkMuqxhcHS94ub7berEc/OlqvbyMKNZ3A
lzuvq0NBZhEUhAVgORAIS17r/q2BvyG4u5LFbG2p0QKBgQDeyyOl+A7xc4lPE2OL
Z3KHJPP4RuUnHnWFC+bNdr5Ag8K7jcjZIcasyUom9rOR0Fpuw9wmXpp3+6fyp9bJ
y6Bi5VioR0ZFP5X+nXxIN3yvgypu6AZvkhHrEFer+heGHxPlbwNKCKMbPzDZPBTZ
vlC7g7xUUcpNmGhrOKr3Qq5FlwKBgQDdgCmRvsHUyzicn8TI3IJBAOcaQG0Yr/R2
FzBqNfHHx7fUZlJfKJsnu9R9VRZmBi4B7MA2xcvz4QrdZWEtY8uoYp8TAGILfW1u
CP4ZHrzfDo/67Uzk2uTMTd0+JOqSm/HiVNguRPvC8EWBoFls+h129GKThMvKR1hP
1oarfAGIiQKBgQCIMAq5gHm59JMhqEt4QqMKo3cS9FtNX1wdGRpbzFMd4q0dstzs
ha4Jnv3Z9YHtBzzQap9fQQMRht6yARDVx8hhy6o3K2J0IBtTSfdXubtZGkfNBb4x
Y0vaseG1uam5jbO+0u5iygbSN/1nPUfNln2JMkzkCh8s8ZYavMgdX0BiPwKBgChR
QL/Hog5yoy5XIoGRKaBdYrNzkKgStwObuvNKOGUt5DckHNA3Wu6DkOzzRO1zKIKv
LlmJ7VLJ3qln36VcaeCPevcBddczkGyb9GxsHOLZCroY4YsykLzjW2cJXy0qd3/E
A8mAQvc7ttsebciZSi2x1BOX82QxUlDN8ptaKglJAoGBAMnLN1TQB0xtWYDPGcGV
2IvgX7OTRRlMVrTvIOvP5Julux9z1r0x0cesl/jaXupsBUlLLicPyBMSBJrXlr24
mrgkodk4TdqO1VtBCZBqak97DHVezstMrbpCGlUD5jBnsHVRLERvS09QlGhqMeNL
jpNQbWH9VhutzbvpYquKrhvK
-----END PRIVATE KEY-----
""", # 2
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNDAzM1oXDTIxMDEwMTAxNDAzM1owFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAypqi
YTni3s60Uo8vgGcFvjWWkB5CD9Fx9pW/2KcxRJ/u137Y+BG8qWMA4lgII3ZIuvo4
6rLDiXnAnDZqUtrvZ90O/gH6RyQqX3AI4EwPvCnRIIe0okRcxnxYBL/LfBY54xuv
46JRYZP4c9IImqQH9QVo2/egtEzcpbmT/mfhpf6NGQWC3Xps2BqDT2SV/DrX/wPA
8P1atE1AxNp8ENxK/cjFAteEyDZOsDSa757ZHKAdM7L8rZ1Fd2xAA1Dq7IyYpTNE
IX72xytWxllcNvSUPLT+oicsSZBadc/p3moc3tR/rNdgrHKybedadru/f9Gwpa+v
0sllZlEcVPSYddAzWwIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQCmk60Nj5FPvemx
DSSQjJPyJoIDpTxQ4luSzIq4hPwlUXw7dqrvHyCWgn2YVe9xZsGrT/+n376ecmgu
sw4s4qVhR9bzKkTMewjC2wUooTA5v9HYsNWZy3Ah7hHPbDHlMADYobjB5/XolNUP
bCM9xALEdM9DxpC4vjUZexlRKmjww9QKE22jIM+bqsK0zqDSq+zHpfHNGGcS3vva
OvI6FPc1fAr3pZpVzevMSN2zufIJwjL4FT5/uzwOCaSCwgR1ztD5CSbQLTLlwIsX
S7h2WF9078XumeRjKejdjEjyH4abKRq8+5LVLcjKEpg7OvktuRpPoGPCEToaAzuv
h+RSQwwY
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDKmqJhOeLezrRS
jy+AZwW+NZaQHkIP0XH2lb/YpzFEn+7Xftj4EbypYwDiWAgjdki6+jjqssOJecCc
NmpS2u9n3Q7+AfpHJCpfcAjgTA+8KdEgh7SiRFzGfFgEv8t8FjnjG6/jolFhk/hz
0giapAf1BWjb96C0TNyluZP+Z+Gl/o0ZBYLdemzYGoNPZJX8Otf/A8Dw/Vq0TUDE
2nwQ3Er9yMUC14TINk6wNJrvntkcoB0zsvytnUV3bEADUOrsjJilM0QhfvbHK1bG
WVw29JQ8tP6iJyxJkFp1z+neahze1H+s12CscrJt51p2u79/0bClr6/SyWVmURxU
9Jh10DNbAgMBAAECggEBALv7Q+Rf+C7wrQDZF6LUc9CrGfq4CGVy2IGJKgqT/jOF
DO9nI1rv4hNr55sbQNneWtcZaYvht2mrzNlj57zepDjDM7DcFuLBHIuWgLXT/NmC
FyZOo3vXYBlNr8EgT2XfnXAp9UWJCmc2CtUzsIYC4dsmXMeTd8kyc5tUl4r5ybTf
1g+RTck/IGgqdfzpuTsNl79FW2rP9z111Py6dbqgQzhuSAune9dnLFvZst8dyL8j
FStETMxBM6jrCF1UcKXzG7trDHiCdzJ8WUhx6opN/8OasQGndwpXto6FZuBy/AVP
4kVQNpUXImYcLEpva0MqGRHg+YN+c84C71CMchnF4aECgYEA7J2go4CkCcZNKCy5
R5XVCqNFYRHjekR+UwH8cnCa7pMKKfP+lTCiBrO2q8zwWwknRMyuycS5g/xbSpg1
L6hi92CV1YQy1/JhlQedekjejNTTuLOPKf78AFNSfc7axDnes2v4Bvcdp9gsbUIO
10cXh0tOSLE7P9y+yC86KQkFAPECgYEA2zO0M2nvbPHv2jjtymY3pflYm0HzhM/T
kPtue3GxOgbEPsHffBGssShBTE3yCOX3aAONXJucMrSAPL9iwUfgfGx6ADdkwBsA
OjDlkxvTbP/9trE6/lsSPtGpWRdJNHqXN4Hx7gXJizRwG7Ym+oHvIIh53aIjdFoE
HLQLpxObuQsCgYAuMQ99G83qQpYpc6GwAeYXL4yJyK453kky9z5LMQRt8rKXQhS/
F0FqQYc1vsplW0IZQkQVC5yT0Z4Yz+ICLcM0O9zEVAyA78ZxC42Io9UedSXn9tXK
Awc7IQkHmmxGxm1dZYSEB5X4gFEb+zted3h2ZxMfScohS3zLI70c6a/aYQKBgQCU
phRuxUkrTUpFZ1PCbN0R/ezbpLbaewFTEV7T8b6oxgvxLxI6FdZRcSYO89DNvf2w
GLCVe6VKMWPBTlxPDEostndpjCcTq3vU+nHE+BrBkTvh14BVGzddSFsaYpMvNm8z
ojiJHH2XnCDmefkm6lRacJKL/Tcj4SNmv6YjUEXLDwKBgF8WV9lzez3d/X5dphLy
2S7osRegH99iFanw0v5VK2HqDcYO9A7AD31D9nwX46QVYfgEwa6cHtVCZbpLeJpw
qXnYXe/hUU3yn5ipdNJ0Dm/ZhJPDD8TeqhnRRhxbZmsXs8EzfwB2tcUbASvjb3qA
vAaPlOSU1wXqhAsG9aVs8gtL
-----END PRIVATE KEY-----
""", # 3
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNDAzNFoXDTIxMDEwMTAxNDAzNFowFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzUqQ
M08E7F2ZE99bFHvpsR6LmgIJOOoGMXacTcEUhRF63E6+730FjxER2a30synv9GGS
3G9FstUmfhyimufkbTumri8Novw5CWZQLiE1rmMBI5nPcR2wAzy9z2odR6bfAwms
yyc3IPYg1BEDBPZl0LCQrQRRU/rVOrbCf7IMq+ATazmBg01gXMzq2M953ieorkQX
MsHVR/kyW0Q0yzhYF1OtIqbXxrdiZ+laTLWNqivj/FdegiWPCf8OcqpcpbgEjlDW
gBcC/vre+0E+16nfUV8xHL5jseJMJqfT508OtHxAzp+2D7b54NvYNIvbOAP+F9gj
aXy5mOvjXclK+hNmDwIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQAjZzTFKG7uoXxm
BPHfQvsKHIB/Cx9zMKj6pLwJzCPHQBzKOMoUen09oq+fb77RM7WvdX0pvFgEXaJW
q/ImooRMo+paf8GOZAuPwdafb2/OGdHZGZ2Cbo/ICGo1wGDCdMvbxTxrDNq1Yae+
m+2epN2pXAO1rlc7ktRkojM/qi3zXtbLjTs3IoPDXWhYPHdI1ThkneRmvxpzB1rW
2SBqj2snvyI+/3k3RHmldcdOrTlgWQ9hq05jWR8IVtRUFFVn9A+yQC3gnnLIUhwP
HJWwTIPuYW25TuxFxYZXIbnAiluZL0UIjd3IAwxaafvB6uhI7v0K789DKj2vRUkY
E8ptxZH4
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEwAIBADANBgkqhkiG9w0BAQEFAASCBKowggSmAgEAAoIBAQDNSpAzTwTsXZkT
31sUe+mxHouaAgk46gYxdpxNwRSFEXrcTr7vfQWPERHZrfSzKe/0YZLcb0Wy1SZ+
HKKa5+RtO6auLw2i/DkJZlAuITWuYwEjmc9xHbADPL3Pah1Hpt8DCazLJzcg9iDU
EQME9mXQsJCtBFFT+tU6tsJ/sgyr4BNrOYGDTWBczOrYz3neJ6iuRBcywdVH+TJb
RDTLOFgXU60iptfGt2Jn6VpMtY2qK+P8V16CJY8J/w5yqlyluASOUNaAFwL++t77
QT7Xqd9RXzEcvmOx4kwmp9PnTw60fEDOn7YPtvng29g0i9s4A/4X2CNpfLmY6+Nd
yUr6E2YPAgMBAAECggEBAIiL6uQl0AmDrBj6vHMghGzp+0MBza6MgngOA6L4JTTp
ToYQ3pEe4D6rxOq7+QHeiBtNd0ilvn9XpVXGqCVOzrIVNiWvaGubRjjJU9WLA1Ct
y4kpekAr1fIhScMXOsh45ub3XXZ27AVBkM5dTlvTpB8uAd0C/TFVqtR10WLsQ99h
Zm9Jczgs/6InYTssnAaqdeCLAf1LbmO4zwFsJfJOeSGGT6WBwlpHwMAgPhg8OLEu
kVWG7BEJ0hxcODk/es/vce9SN7BSyIzNY+qHcGtsrx/o0eO2Av/Z7ltV4Sz6UN1K
0y0OTiDyT/l62U2OugSN3wQ4xPTwlrWl7ZUHJmvpEaECgYEA+w2JoB2i1OV2JTPl
Y0TKSKcZYdwn7Nwh4fxMAJNJ8UbpPqrZEo37nxqlWNJrY/jKX3wHVk4ESSTaxXgF
UY7yKT0gRuD9+vE0gCbUmJQJTwbceNJUu4XrJ6SBtf72WgmphL+MtyKdwV8XltVl
Yp0hkswGmxl+5+Js6Crh7WznPl8CgYEA0VYtKs2YaSmT1zraY6Fv3AIQZq012vdA
7nVxmQ6jKDdc401OWARmiv0PrZaVNiEJ1YV8KxaPrKTfwhWqxNegmEBgA1FZ66NN
SAm8P9OCbt8alEaVkcATveXTeOCvfpZUO3sqZdDOiYLiLCsokHblkcenK85n0yT6
CzhTbvzDllECgYEAu9mfVy2Vv5OK2b+BLsw0SDSwa2cegL8eo0fzXqLXOzCCKqAQ
GTAgTSbU/idEr+NjGhtmKg/qaQioogVyhVpenLjeQ+rqYDDHxfRIM3rhlD5gDg/j
0wUbtegEHrgOgcSlEW16zzWZsS2EKxq16BoHGx6K+tcS/FOShg5ASzWnuiUCgYEA
sMz+0tLX8aG7CqHbRyBW8FMR9RY/kRMY1Q1+Bw40wMeZfSSSkYYN8T9wWWT/2rqm
qp7V0zJ34BFUJoDUPPH84fok3Uh9EKZYpAoM4z9JP0jREwBWXMYEJnOQWtwxfFGN
DLumgF2Nwtg3G6TL2s+AbtJYH4hxagQl5woIdYmnyzECgYEAsLASpou16A3uXG5J
+5ZgF2appS9Yfrqfh6TKywMsGG/JuiH3djdYhbJFIRGeHIIDb4XEXOHrg/SFflas
If0IjFRh9WCvQxnoRha3/pKRSc3OEka1MR/ZREK/d/LQEPmsRJVzY6ABKqmPAMDD
5CnG6Hz/rP87BiEKd1+3PGp8GCw=
-----END PRIVATE KEY-----
""", # 4
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNDAzNFoXDTIxMDEwMTAxNDAzNFowFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0sap
75YbbkEL85LFava3FrO1jpgVteQ4NGxxy1Nu9w2hPfMMeCPWjB8UfAwFk+LVPyvW
LAXd1zWL5rGpQ2ytIVQlTraR5EnALA1sMcQYbFz1ISPTYB031bEN/Ch8JWYwCG5A
X2H4D6BC7NgT6YyWDt8vxQnqAisPHQ/OK4ABD15CwkTyPimek2/ufYN2dapg1xhG
IUD96gqetJv9bu0r869s688kADIComsYG+8KKfFN67S3rSHMIpZPuGTtoHGnVO89
XBm0vNe0UxQkJEGJzZPn0tdec0LTC4GNtTaz5JuCjx/VsJBqrnTnHHjx0wFz8pff
afCimRwA+LCopxPE1QIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQBOkAnpBb3nY+dG
mKCjiLqSsuEPqpNiBYR+ue/8aVDnOKLKqAyQuyRZttQ7bPpKHaw7pwyCZH8iHnt6
pMCLCftNSlV2Fa8msRmuf5AiGjUvR1M8VtHWNYE8pedWrJqUgBhF/405B99yd8CT
kQJXKF18LObj7YKNsWRoMkVgqlQzWDMEqbfmy9MhuLx2EZPsTB1L0BHNGGDVBd9o
cpPLUixcc12u+RPMKq8x3KgwsnUf5vX/pCnoGcCy4JahWdDgcZlf0hUKGT7PUem5
CWW8SMeqSWQX9XpE5Qlm1+W/QXdDXLbbHqDtvBeUy3iFQe3C9RSkp0qdutxkAlFk
f5QHXfJ7
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDSxqnvlhtuQQvz
ksVq9rcWs7WOmBW15Dg0bHHLU273DaE98wx4I9aMHxR8DAWT4tU/K9YsBd3XNYvm
salDbK0hVCVOtpHkScAsDWwxxBhsXPUhI9NgHTfVsQ38KHwlZjAIbkBfYfgPoELs
2BPpjJYO3y/FCeoCKw8dD84rgAEPXkLCRPI+KZ6Tb+59g3Z1qmDXGEYhQP3qCp60
m/1u7Svzr2zrzyQAMgKiaxgb7wop8U3rtLetIcwilk+4ZO2gcadU7z1cGbS817RT
FCQkQYnNk+fS115zQtMLgY21NrPkm4KPH9WwkGqudOccePHTAXPyl99p8KKZHAD4
sKinE8TVAgMBAAECggEALU5EotoqJUXYEtAenUJQ0pFoWjE4oXNf3Wzd/O1/MZ19
ZjqDGKPjbxUTKyLOZB5i5gQ/MhFEwQiifMD9eB+5CyvyJPw7Wc28f/uWoQ/cjBZj
Hm979PHy2X0IW4Y8QTG462b/cUE2t+0j1ZMQnKf6bVHuC7V41mR5CC8oitMl5y5g
34yJmWXlIA0ep/WotLMqvil6DnSM/2V8Ch4SxjnzPpjbe4Kj+woucGNr4UKstZER
8iuHTsR64LjoGktRnnMwZxGZQI7EC428zsliInuWMdXe//w2chLdkirqpSrIQwSZ
3jNWStqBXGYaRg5Z1ilBvHtXxkzDzbAlzRBzqfEwwQKBgQDqYdMRrzHJaXWLdsyU
6jAuNX9tLh7PcicjP93SbPujS6mWcNb+D/au+VhWD+dZQDPRZttXck7wvKY1lw1V
MK0TYI7ydf8h3DFx3Mi6ZD4JVSU1MH233C3fv/FHenDoOvMXXRjUZxaRmuzFJvzt
6QlKIfSvwT+1wrOACNfteXfZUQKBgQDmN3Uuk01qvsETPwtWBp5RNcYhS/zGEQ7o
Q4K+teU453r1v8BGsQrCqulIZ3clMkDru2UroeKn1pzyVAS2AgajgXzfXh3VeZh1
vHTLP91BBYZTTWggalEN4aAkf9bxX/hA+9Bw/dzZcQW2aNV7WrYuCSvp3SDCMina
anQq/PaSRQKBgHjw23HfnegZI89AENaydQQTFNqolrtiYvGcbgC7vakITMzVEwrr
/9VP0pYuBKmYKGTgF0RrNnKgVX+HnxibUmOSSpCv9GNrdJQVYfpT6XL1XYqxp91s
nrs7FuxUMNiUOoWOw1Yuj4W4lH4y3QaCXgnDtbfPFunaOrdRWOIv8HjRAoGAV3NT
mSitbNIfR69YIAqNky3JIJbb42VRc1tJzCYOd+o+pCF96ZyRCNehnDZpZQDM9n8N
9GAfWEBHCCpwS69DVFL422TGEnSJPJglCZwt8OgnWXd7CW05cvt1OMgzHyekhxLg
4Dse7J5pXBxAlAYmVCB5xPGR4xLpISX1EOtcwr0CgYEA5rA2IUfjZYb4mvFHMKyM
xWZuV9mnl3kg0ULttPeOl3ppwjgRbWpyNgOXl8nVMYzxwT/A+xCPA18P0EcgNAWc
frJqQYg3NMf+f0K1wSaswUSLEVrQOj25OZJNpb21JEiNfEd5DinVVj4BtVc6KSpS
kvjbn2WhEUatc3lPL3V0Fkw=
-----END PRIVATE KEY-----
""", # 5
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNTExM1oXDTIxMDEwMTAxNTExM1owFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1c5y
S9IZHF9MIuwdafzhMkgP37I3RVpHEbpnPwnLFqSWelS5m2eDkwWd5SkfGjrmQ5q0
PEpqLlh3zHGw9yQjnHS3CCS1PwQ1kmwvpIK3HM5y8GM7ry1zkam8ZR4iX6Y7VG9g
9mhiVVFoVhe1gHeiC/3Mp6XeNuEiD0buM+8qZx9B21I+iwzy4wva7Gw0fJeq9G1c
lq2rhpD1LlIEodimWOi7lOEkNmUiO1SvpdrGdxUDpTgbdg6r5pCGjOXLd74tAQHP
P/LuqRNJDXtwvHtLIVQnW6wjjy4oiWZ8DXOdc9SkepwQLIF5Wh8O7MzF5hrd6Cvw
SOD3EEsJbyycAob6RwIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQBDNcbKVUyGOAVm
k3iVuzkkkymlTAMm/gsIs6loLJrkSqNg160FdVKJoZFjQtqoqLgLrntdCJ377nZ9
1i+yzbZsA4DA7nxj0IEdnd7rRYgGLspGqWeKSTROATeT4faLTXenecm0v2Rpxqc7
dSyeZJXOd2OoUu+Q64hzXCDXC6LNM+xZufxV9qv+8d+CipV6idSQZaUWSVuqFCwD
PT0R4eWfkMMaM8QqtNot/hVCEaKT+9rG0mbpRe/b/qBy5SR0u+XgGEEIV+33L59T
FXY+DpI1Dpt/bJFoUrfj6XohxdTdqYVCn1F8in98TsRcFHyH1xlkS3Y0RIiznc1C
BwAoGZ4B
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDVznJL0hkcX0wi
7B1p/OEySA/fsjdFWkcRumc/CcsWpJZ6VLmbZ4OTBZ3lKR8aOuZDmrQ8SmouWHfM
cbD3JCOcdLcIJLU/BDWSbC+kgrccznLwYzuvLXORqbxlHiJfpjtUb2D2aGJVUWhW
F7WAd6IL/cynpd424SIPRu4z7ypnH0HbUj6LDPLjC9rsbDR8l6r0bVyWrauGkPUu
UgSh2KZY6LuU4SQ2ZSI7VK+l2sZ3FQOlOBt2DqvmkIaM5ct3vi0BAc8/8u6pE0kN
e3C8e0shVCdbrCOPLiiJZnwNc51z1KR6nBAsgXlaHw7szMXmGt3oK/BI4PcQSwlv
LJwChvpHAgMBAAECggEBAK0KLeUBgIM++Y7WDCRInzYjrn08bpE5tIU7mO4jDfQg
dw1A3wtQZuOpyxW6B0siWlRis/aLv44M2cBkT3ZmEFBDAhOcKfh7fqQn3RNHG847
pDi8B4UKwxskBa7NCcLh9eirUA19hABLJ6dt/t6fdE5CNc2FZ+iAoyE8JfNwYKAd
6Fa3HqUBPNWt8ryj4ftgpMNBdfmLugEM4N20SXJA28hOq2lUcwNKQQ1xQrovl0ig
iMbMWytV4gUPKC9Wra66OYIkk/K8teiUNIYA4JwAUVTs1NEWoyfwUTz1onutCkMl
5vY7JAqRoDWoSUX6FI+IHUdyqPAMdOMhC37gjrxoo2ECgYEA7trDMu6xsOwEckDh
iz148kejMlnTTuCNetOFBw3njFgxISx0PrDLWmJmnHMxPv9AAjXYb2+UCCm3fj6Q
OB8o4ZJm0n504qbFHcb2aI22U5hZ99ERvqx8WBnJ2RarIBmg06y0ktxq8gFR2qxF
0hWAOcDn1DWQ8QI0XBiFFcJTGtcCgYEA5SdlIXRnVZDKi5YufMAORG9i74dXUi0Y
02UoVxJ+q8VFu+TT8wrC5UQehG3gX+79Cz7hthhDqOSCv6zTyE4Evb6vf9OLgnVe
E5iLF033zCxLSS9MgiZ+jTO+wK3RsapXDtGcSEk2P82Pj5seNf4Ei1GNCRlm1DbX
71wlikprHhECgYABqmLcExAIJM0vIsav2uDiB5/atQelMCmsZpcx4mXv85l8GrxA
x6jTW4ZNpvv77Xm7yjZVKJkGqYvPBI6q5YS6dfPjmeAkyHbtazrCpeJUmOZftQSD
qN5BGwTuT5sn4SXe9ABaWdEhGONCPBtMiLvZK0AymaEGHTbSQZWD/lPoBwKBgGhk
qg2zmd/BNoSgxkzOsbE7jTbR0VX+dXDYhKgmJM7b8AjJFkWCgYcwoTZzV+RcW6rj
2q+6HhizAV2QvmpiIIbQd+Mj3EpybYk/1R2ox1qcUy/j/FbOcpihGiVtCjqF/2Mg
2rGTqMMoQl6JrBmsvyU44adjixTiZz0EHZYCkQoBAoGBAMRdmoR4mgIIWFPgSNDM
ISLJxKvSFPYDLyAepLfo38NzKfPB/XuZrcOoMEWRBnLl6dNN0msuzXnPRcn1gc1t
TG7db+hivAyUoRkIW3dB8pRj9dDUqO9OohjKsJxJaQCyH5vPkQFSLbTIgWrHhU+3
oSPiK/YngDV1AOmPDH7i62po
-----END PRIVATE KEY-----
""", #6
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNTExMloXDTIxMDEwMTAxNTExMlowFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAojGu
fQaTVT9DJWJ/zogGfrryEJXYVy9c441O5MrLlRx7nCIWIUs2NEhHDJdqJjYOTdmk
K98VhdMpDPZwxjgvvZrh43lStBRIW3zZxv747rSl2VtpSqD/6UNWJe5u4SR7oga4
JfITOKHg/+ASxnOxp/iu6oT6jBL6T7KSPh6Rf2+it2rsjhktRreFDJ2hyroNq1w4
ZVNCcNPgUIyos8u9RQKAWRNchFh0p0FCS9xNrn3e+yHnt+p6mOOF2gMzfXT/M2hq
KQNmc5D3yNoH2smWoz7F3XsRjIB1Ie4VWoRRaGEy7RwcwiDfcaemD0rQug6iqH7N
oomF6f3R4DyvVVLUkQIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQB/8SX6qyKsOyex
v3wubgN3FPyU9PqMfEzrFM6X5sax0VMVbSnekZrrXpdnXYV+3FBu2GLLQc900ojj
vKD+409JIriTcwdFGdLrQPTCRWkEOae8TlXpTxuNqJfCPVNxFN0znoat1bSRsX1U
K0mfEETQ3ARwlTkrF9CM+jkU3k/pnc9MoCLif8P7OAF38AmIbuTUG6Gpzy8RytJn
m5AiA3sds5R0rpGUu8mFeBpT6jIA1QF2g+QNHKOQcfJdCdfqTjKw5y34hjFqbWG9
RxWGeGNZkhC/jADCt+m+R6+hlyboLuIcVp8NJw6CGbr1+k136z/Dj+Fdhm6FzF7B
qULeRQJ+
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCiMa59BpNVP0Ml
Yn/OiAZ+uvIQldhXL1zjjU7kysuVHHucIhYhSzY0SEcMl2omNg5N2aQr3xWF0ykM
9nDGOC+9muHjeVK0FEhbfNnG/vjutKXZW2lKoP/pQ1Yl7m7hJHuiBrgl8hM4oeD/
4BLGc7Gn+K7qhPqMEvpPspI+HpF/b6K3auyOGS1Gt4UMnaHKug2rXDhlU0Jw0+BQ
jKizy71FAoBZE1yEWHSnQUJL3E2ufd77Iee36nqY44XaAzN9dP8zaGopA2ZzkPfI
2gfayZajPsXdexGMgHUh7hVahFFoYTLtHBzCIN9xp6YPStC6DqKofs2iiYXp/dHg
PK9VUtSRAgMBAAECggEANjn0A3rqUUr4UQxwfIV/3mj0O1VN4kBEhxOcd+PRUsYW
EapXycPSmII9ttj8tU/HUoHcYIqSMI7bn6jZJXxtga/BrALJAsnxMx031k8yvOQK
uvPT7Q6M4NkReVcRHRbMeuxSLuWTRZDhn8qznEPb9rOvD1tsRN6nb3PdbwVbUcZh
2F6JDrTyI/Df6nrYQAWOEe2ay7tzgrNYE4vh+DW7oVmyHRgFYA+DIG5Q+7OVWeW5
bwYYPKlo4/B0L+GfMKfMVZ+5TvFWAK0YD1e/CW1Gv+i/8dWm4O7UNGg5mTnrIcy1
g5wkKbyea02/np2B/XBsSWXDl6rTDHL7ay0rH2hjEQKBgQDMKSm3miQTIcL/F2kG
ieapmRtSc7cedP967IwUfjz4+pxPa4LiU47OCGp1bmUTuJAItyQyu/5O3uLpAriD
PTU+oVlhqt+lI6+SJ4SIYw01/iWI3EF2STwXVnohWG1EgzuFM/EqoB+mrodNONfG
UmP58vI9Is8fdugXgpTz4Yq9pQKBgQDLYJoyMVrYTvUn5oWft8ptsWZn6JZXt5Bd
aXh+YhNmtCrSORL3XjcH4yjlcn7X8Op33WQTbPo7QAJ1CumJzAI88BZ/8za638xb
nLueviZApCt0bNMEEdxDffxHFc5TyHE+obMKFfApbCnD0ggO6lrZ8jK9prArLOCp
mRU9SSRffQKBgAjoBszeqZI4F9SfBdLmMyzU5A89wxBOFFMdfKLsOua1sBn627PZ
51Hvpg1HaptoosfujWK1NsvkB0wY9UmsYuU/jrGnDaibnO4oUSzN/WaMlsCYszZg
zYFLIXrQ67tgajlOYcf1Qkw4MujYgPlC4N+njI/EM/rwagGUjcDx5uaNAoGASyqz
EuYG63eTSGH89SEaohw0+yaNmnHv23aF4EAjZ4wjX3tUtTSPJk0g6ly84Nbb8d1T
hZJ7kbaAsf2Mfy91jEw4JKYhjkP05c8x0OP6g12p6efmvdRUEmXX/fXjQjgNEtb0
sz+UedrOPN+9trWLSo4njsyyw+JcTpKTtQj5dokCgYEAg9Y3msg+GvR5t/rPVlKd
keZkrAp0xBJZgqG7CTPXWS1FjwbAPo7x4ZOwtsgjCuE52lar4j+r2Il+CDYeLfxN
h/Jfn6S9ThUh+B1PMvKMMnJUahg8cVL8uQuBcbAy8HPRK78WO2BTnje44wFAJwTc
0liuYqVxZIRlFLRl8nGqog8=
-----END PRIVATE KEY-----
""", #7
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNTExMloXDTIxMDEwMTAxNTExMlowFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu9oO
cFlNukUcLfFrfkEaUiilcHLmn5OokQbj95CGd2ehQCCVwrkunYLBisthRaancFFb
/yM998B0IUsKTsoLi5DAN3/SkSm6GiQIGO05E4eBPljwJ61QQMxh8+1TwQ9HTun1
ZE1lhVN1aRmI9VsbyTQLjXh9OFNLSJEKb29mXsgzYwYwNOvo+idzXpy4bMyNoGxY
Y+s2FIKehNHHCv4ravDn8rf6DtDOvyN4d0/QyNws9FpAZMXmLwtBJ9exOqKFW43w
97NxgdNiTFyttrTKTi0b+9v3GVdcEZw5b2RMIKi6ZzPof6/0OlThK6C3xzFK3Bp4
PMjTfXw5yyRGVBnZZwIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQA4Ms6LqzMu757z
bxISiErRls6fcnq0fpSmiPNHNKM7YwG9KHYwPT6A0UMt30zDwNOXCQBI19caGeeO
MLPWa7Gcqm2XZB2jQwvLRPeFSy9fm6RzJFeyhrh/uFEwUetwYmi/cqeIFDRDBQKn
bOaXkBk0AaSmI5nRYfuqpMMjaKOFIFcoADw4l9wWhv6DmnrqANzIdsvoSXi5m8RL
FcZQDZyHFlHh3P3tLkmQ7ErM2/JDwWWPEEJMlDm/q47FTOQSXZksTI3WRqbbKVv3
iQlJjpgi9yAuxZwoM3M4975iWH4LCZVMCSqmKCBt1h9wv4LxqX/3kfZhRdy1gG+j
41NOSwJ/
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQC72g5wWU26RRwt
8Wt+QRpSKKVwcuafk6iRBuP3kIZ3Z6FAIJXCuS6dgsGKy2FFpqdwUVv/Iz33wHQh
SwpOyguLkMA3f9KRKboaJAgY7TkTh4E+WPAnrVBAzGHz7VPBD0dO6fVkTWWFU3Vp
GYj1WxvJNAuNeH04U0tIkQpvb2ZeyDNjBjA06+j6J3NenLhszI2gbFhj6zYUgp6E
0ccK/itq8Ofyt/oO0M6/I3h3T9DI3Cz0WkBkxeYvC0En17E6ooVbjfD3s3GB02JM
XK22tMpOLRv72/cZV1wRnDlvZEwgqLpnM+h/r/Q6VOEroLfHMUrcGng8yNN9fDnL
JEZUGdlnAgMBAAECggEALlZdlW0R9U6y4spYf65Dddy84n4VUWu0+wE+HoUyBiYz
6oOfLYdMbmIgp8H/XpT7XINVNBxXXtPEUaoXAtRoAKdWItqO8Gvgki4tKSjrGVwl
j2GU69SepT1FNExoiojgSCEB/RnyXu71WVWJKSyuL/V8nAsKqGgze9T7Q/2wvNQt
SQqLxZlrWF0P8WqaAiSrHV4GnDrdeF+k1KBo2+pSaDNv6cNwOyVG8EII9tqhF8kj
6nD6846ish6OqmlSisaSGopJZL1DCQzszFMxKd2+iBDY7Kn6hVIhRaNnaZUFhpKM
dNh6hBqOycMepAp0sz5pdo+fxpifkoR/cPWgyC3QkQKBgQDixe9VsiZ7u2joxF/9
JcAExKhqE28OUmIwt6/j+uzYShxN6Oo9FUo3ICtAPCCFsjhvb3Qum7FspmxrqtNy
fzclibZJPO8ey2PzqaiOfiVfgJmNSvoCOdgM4OqFLtRO6eSTzhJeI4VPrPcq/5la
0FuOi1WZs/Au9llqLqGSDH3UAwKBgQDUD/bSJbOk5SvNjFtFm0ClVJr66mJ5e4uN
4VGv8KGFAJ+ExIxujAukfKdwLjS1wEy2RePcshfT8Y9FVh/Q1KzzrQi3Gwmfq1G6
Dpu2HlJpaZl+9T81x2KS8GP3QNczWMe2nh7Lj+6st+b4F+6FYbVTFnHaae27sXrD
XPX15+uxzQKBgGy+pBWBF4kwBo/QU4NuTdU7hNNRPGkuwl1ASH1Xv6m8aDRII8Nk
6TDkITltW98g5oUxehI7oOpMKCO9SCZYsNY0YpBeQwCOYgDfc6/Y+A0C+x9RO/BD
UsJiPLPfD/pDmNPz9sTj3bKma+RXq29sCOujD0pkiiHLCnerotkJWnGHAoGAAkCJ
JoIv/jhQ1sX+0iZr8VWMr819bjzZppAWBgBQNtFi4E4WD7Z9CSopvQ9AkA2SwvzL
BrT9e8q88sePXvBjRdM4nHk1CPUQ0SEGllCMH4J3ltmT6kZLzbOv3BhcMLdop4/W
U+MbbcomMcxPRCtdeZxraR5m3+9qlliOZCYqYqECgYA5eLdxgyHxCS33QGFHRvXI
TLAHIrr7wK1xwgkmZlLzYSQ8Oqh1UEbgoMt4ulRczP2g7TCfvANw2Sw0H2Q5a6Fj
cnwVcXJ38DLg0GCPMwzE8dK7d8tKtV6kGiKy+KFvoKChPjE6uxhKKmCJaSwtQEPS
vsjX3iiIgUQPsSz8RrNFfQ==
-----END PRIVATE KEY-----
""", #8
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNTExMloXDTIxMDEwMTAxNTExMlowFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA5DNu
CKhhl6wCbgoCkFemwJh3ATbAjhInHpvQWIFDfSK1USElCKxqosIxiBQCx3Zs2d/U
GeIA7QAM2atNdXaateacEaKMmGE9LEtO0Dg5lmT43WzmGkG9NmCwK3JjAekc5S9d
HKNtEQo7o8RKfj81zlDSq2kzliy98cimk24VBBGkS2Cn7Vy/mxMCqWjQazTXbpoS
lXw6LiY5wFXQmXOB5GTSHvqyCtBQbOSSbJB77z/fm7bufTDObufTbJIq53WPt00Y
f+JNnzkX1X0MaBCUztoZwoMaExWucMe/7xsQ46hDn6KB4b0lZk+gsK45QHxvPE1R
72+ZkkIrGS/ljIKahQIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQDib1653CneSmy2
gYzGeMlrI05Jqo3JuHNMQHzAjIrb4ee57VA4PTQa1ygGol/hVv6eTvZr3p2ospDS
5Kfwj1HLO4jSMX1Bnm1FG0naQogz2CD3xfYjbYOVRhAxpld1MNyRveIOhDRARY7N
XNAaNPZ1ALrwbENSYArr18xDzgGWe/dgyRCEpCFIsztiA+7jGvrmAZgceIE8K3h3
fkvNmXBH58ZHAGTiyRriBZqS+DXrBrQOztXSJwFnOZnRt6/efeBupt8j5hxVpBLW
vtjpBc23uUcbbHOY2AW2Bf+vIr4/LmJ/MheKV+maa2990vmC93tvWlFfc74mgUkW
HJfXDmR6
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDkM24IqGGXrAJu
CgKQV6bAmHcBNsCOEicem9BYgUN9IrVRISUIrGqiwjGIFALHdmzZ39QZ4gDtAAzZ
q011dpq15pwRooyYYT0sS07QODmWZPjdbOYaQb02YLArcmMB6RzlL10co20RCjuj
xEp+PzXOUNKraTOWLL3xyKaTbhUEEaRLYKftXL+bEwKpaNBrNNdumhKVfDouJjnA
VdCZc4HkZNIe+rIK0FBs5JJskHvvP9+btu59MM5u59NskirndY+3TRh/4k2fORfV
fQxoEJTO2hnCgxoTFa5wx7/vGxDjqEOfooHhvSVmT6CwrjlAfG88TVHvb5mSQisZ
L+WMgpqFAgMBAAECggEABTdPuo7uvCLIY2+DI319aEWT4sk3mYe8sSxqlLtPqZqT
fmk9iXc3cMTzkOK0NY71af19waGy17f6kzchLCAr5SCCTLzkbc87MLn/8S530oI4
VgdZMxxxkL6hCD0zGiYT7QEqJa9unMcZGeMwuLYFKtQaHKTo8vPO26n0dMY9YLxj
cNUxsKLcKk8dbfKKt4B4fZgB7nU0BG9YbKYZ3iZ7/3mG+6jA6u+VYc/WHYQjTmpL
oLFN7NOe3R7jIx/kJ1OqNWqsFoLpyiiWd1Mr0l3EdD1kCudptMgD8hd++nx2Yk2w
K4+CpOVIN/eCxDDaAOJgYjCtOayVwUkDAxRRt9VnAQKBgQD5s1j6RJtBNTlChVxS
W3WpcG4q8933AiUY/Chx0YTyopOiTi7AGUaA8AOLFBcO2npa+vzC+lvuOyrgOtVW
sD10H2v5jNKlbeBp+Q9rux2LAyp4TvzdXWKhVyZrdtITF0hn6vEYNp7MtyWRFb1O
3Ie5HQBPHtzllFOMynacjOdjpQKBgQDp9TrbfOmwGWmwPKmaFKuy8BKxjJM+ct0X
4Xs1uSy9Z9Y8QlDNbNaooI8DA1NY0jDVHwemiGC4bYsBNKNRcbI0s2nr0hQMft42
P/NpugHv0YXiVz+5bfim4woTiHHbfREqchlIGo3ryClAiDU9fYZwTOtb9jPIhX3G
9v+OsoMlYQKBgQDJUQW90S5zJlwh+69xXvfAQjswOimNCpeqSzK4gTn0/YqV4v7i
Nf6X2eqhaPMmMJNRYuYCtSMFMYLiAc0a9UC2rNa6/gSfB7VU+06phtTMzSKimNxa
BP6OIduB7Ox2I+Fmlw8GfJMPbeHF1YcpW7e5UV58a9+g4TNzYZC7qwarWQKBgQCA
FFaCbmHonCD18F/REFvm+/Lf7Ft3pp5PQouXH6bUkhIArzVZIKpramqgdaOdToSZ
SAGCM8rvbFja8hwurBWpMEdeaIW9SX8RJ/Vz/fateYDYJnemZgPoKQcNJnded5t8
Jzab+J2VZODgiTDMVvnQZOu8To6OyjXPRM0nK6cMQQKBgQDyX44PHRRhEXDgJFLU
qp2ODL54Qadc/thp2m+JmAvqmCCLwuYlGpRKVkLLuZW9W6RlVqarOC3VD3wX5PRZ
IsyCGLi+Jbrv9JIrYUXE80xNeQVNhrrf02OW0KHbqGxRaNOmp1THPw98VUGR2J/q
YAp6XUXU7LEBUrowye+Ty2o7Lg==
-----END PRIVATE KEY-----
""", #9
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNTExMVoXDTIxMDEwMTAxNTExMVowFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA1k2R
PWYihftppo3CoxeseFwgg7guxZVkP7aAur5uBzSeAB7sBG1G2bRrwMX71S4xPwot
zYiEoxUrTStUqEKjL2aozfHsXnHZ7kwwUgZFDZUg+ve2tZDA3HCUr4tLYKlyFqpx
2nCouc45MjQ4wAxRl4rQxIUG2uSTzvP+xXtjoJYMIEEyCpcsRXfqfVkEUe9nrPsF
0Ibzk7Cyt75HDI4uEzBuHux0DYuGy6R02jz/vf/dIZ4WepjSY06xpblTHZgieDRX
fU2+YOcvb0eDHyA8Q5p8ropK71MNIP5+kffFd90SVr4EkCA8S+cd6FdKQasRr+jF
9MUhMS4ObvlrYTG+hwIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQCy62MZ3+59/VpX
c9Hsmb4/BMWt0irLJit4w4SkuYKGFLCMKZI4LN4pEkXaiE1eqF2DNS1qOvl5luty
Zz4oggrqilwuFeH98o9Zeg9SYnouuypORVP/3DPbJF/jiQg5J8kJb1sy+BjRiT8I
5X6/cCBYT+MljFz5tpqWOtWTgA30e1BV8JFj8F4dgUcWsAVT/I4l9zgMLUnhcO6E
wLtEE0I6aT1RHJB28ndwJzj4La98Oirw7LAEAWbExWYB90ypLaGY+JVJe3f5fijC
fJpQ2mbs4syXDmb5bU2C2pGPTKZPcyx15iQrq1uHInD0facOw+pmllAFxuG96lA1
+o2VzKwP
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDWTZE9ZiKF+2mm
jcKjF6x4XCCDuC7FlWQ/toC6vm4HNJ4AHuwEbUbZtGvAxfvVLjE/Ci3NiISjFStN
K1SoQqMvZqjN8execdnuTDBSBkUNlSD697a1kMDccJSvi0tgqXIWqnHacKi5zjky
NDjADFGXitDEhQba5JPO8/7Fe2OglgwgQTIKlyxFd+p9WQRR72es+wXQhvOTsLK3
vkcMji4TMG4e7HQNi4bLpHTaPP+9/90hnhZ6mNJjTrGluVMdmCJ4NFd9Tb5g5y9v
R4MfIDxDmnyuikrvUw0g/n6R98V33RJWvgSQIDxL5x3oV0pBqxGv6MX0xSExLg5u
+WthMb6HAgMBAAECggEAeCyRSNwQeg/NZD/UqP6qkegft52+ZMBssinWsGH/c3z3
KVwtwCHDfGvnjPe5TAeWSCKeIsbukkFZwfGNjLmppvgrqymCAkhYDICfDDBF4uMA
1pu40sJ01Gkxh+tV/sOmnb1BEVzh0Sgq/NM6C8ActR18CugKOw+5L3G2KeoSqUbT
2hcPUsnik10KwqW737GQW4LtEQEr/iRmQkxI3+HBzvPWjFZzjOcpUph+FW5TXtaU
T26mt1j+FjbdvvhCuRMY/VZBJ5h1RKU95r57F1AjW/C0RRJ8FxR1CeSy4IlmQBrh
6wAa3Tdm0k/n4ZspC9bF5eVTJEtb0AohiYZrIa8MuQKBgQD8yjCLYa41H304odCx
NwPRJcmlIk5YGxPrhHAT9GEgU6n/no7YMVx1L7fNLcMjAyx54jauEU7J19Aki7eV
SIdU9TwqmkOAFfM6TOEJZiOi66gABOxeK2yDyfmR6Apaw3caku4O058t4KVwHSCB
DanYCMzxCBqS9jUTTyAh0fMg6wKBgQDZBkIukg3FKPor5LzkUXIKnNHYPfHbERHw
piWS6GZwqhuWNlOCWxiBR4rEUU/RbFQZw/FCi5OuAk2lBC0LBmC0/Sz4/+xDdCbv
uNhMOTRcy9nFVpmpIWCx4N/KmXHEuFxli/JNXux7iki74AVC9VPrAt/kCvwf06Df
oDb8ljdR1QKBgQChVOD6c5Lc8IXYeN1Z3IShHH6+11AsxstFyjZFZff+y6Z5L1Z2
/7nESHoDhqs9Uy81cnv3R7CC/Ssnx8uYiLtmK0UE44Mk4d1jXeFZQEiKF+AWcw3v
Y8NTsLmItxC0sH75BMDN0Z2LiA3Nqaku8+trpuI1Cjj7hgqFkkAtlXKXlQKBgBMb
c/Q5s7CqHOyEZQUNDqdUiz0opwSMijHPzvsSLwK4V1lwSwXtE0k+jT8fkZF0oirq
j3E2bLgjR8bBiV2xIA6PQ8hgb+K4dT0h3xlG6A9Le07egwTbBXJjxBBIVjXlrWzb
V2fsdZGi6ShxXsU4aD0GscOYG/6JWV6W8oBmkVRJAoGAepIZ+OYmFjb7uxdh4EtP
hluEtx5bLOLuo6c0S149omUXUhbsuyzTZS6Ip9ySDMnK3954c4Q4WJ4yQKixQNVq
78aDfy4hP/8TE/Q9CRddUof2P33PJMhVNqzTRYMpqV+zxifvtw3hoDTLKHTQxCR2
M1+O4VvokU5pBqUpGXiMDfs=
-----END PRIVATE KEY-----
""", #10
"""-----BEGIN CERTIFICATE-----
MIICojCCAYoCAQEwDQYJKoZIhvcNAQELBQAwFzEVMBMGA1UEAwwMbmV3cGJfdGhp
bmd5MB4XDTIwMDEwMjAxNTExMVoXDTIxMDEwMTAxNTExMVowFzEVMBMGA1UEAwwM
bmV3cGJfdGhpbmd5MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnbCU
M37hG7zrCyyJEI6pZmOomnI+CozbP5KAhWSV5y7R5H6lcAEG2UDV+lCUxHT2ufOa
i1H16bXyBt7VoMTHIH50S58NUCUEXcuRWVR16tr8CzcTHQAkfIrmhY2XffPilX7h
aw35UkoVmXcqSDNNJD6jmvWexvmbhzVWW8Vt5Pivet2/leVuqPXB54/alSbkC74m
x6X5XKQc6eyPsb1xvNBuiSpFzdqbEn7lUwj6jFTkh9tlixgmgx+J0XoQXbawyrAg
rcIQcse/Ww+KBA1KSccFze+XBTbIull4boYhbJqkb6DW5bY7/me2nNxE9DRGwq+S
kBsKq3YKeCf8LEhfqQIDAQABMA0GCSqGSIb3DQEBCwUAA4IBAQAD+tWGFhINYsWT
ibKWlCGgBc5uB7611cLCevx1yAL6SaOECVCQXzaaXIaETSbyY03UO2yBy3Pl10FV
GYXLrAWTFZsNVJm55XIibTNw1UBPNwdIoCSzAYuOgMF0GHhTTQU0hNYWstOnnE2T
6lSAZQZFkaW4ZKs6sUp42Em9Bu99PehyIgnw14qb9NPg5qKdi2GAvkImZCrGpMdK
OF31U7Ob0XQ0lxykcNgG4LlUACd+QxLfNpmLBZUGfikexYa1VqBFm3oAvTt8ybNQ
qr7AKXDFnW75aCBaMpQWzrstA7yYZ3D9XCd5ZNf6d08lGM/oerDAIGnZOZPJgs5U
FaWPHdS9
-----END CERTIFICATE-----
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCdsJQzfuEbvOsL
LIkQjqlmY6iacj4KjNs/koCFZJXnLtHkfqVwAQbZQNX6UJTEdPa585qLUfXptfIG
3tWgxMcgfnRLnw1QJQRdy5FZVHXq2vwLNxMdACR8iuaFjZd98+KVfuFrDflSShWZ
dypIM00kPqOa9Z7G+ZuHNVZbxW3k+K963b+V5W6o9cHnj9qVJuQLvibHpflcpBzp
7I+xvXG80G6JKkXN2psSfuVTCPqMVOSH22WLGCaDH4nRehBdtrDKsCCtwhByx79b
D4oEDUpJxwXN75cFNsi6WXhuhiFsmqRvoNbltjv+Z7ac3ET0NEbCr5KQGwqrdgp4
J/wsSF+pAgMBAAECggEAPSu1ofBTRN5ZU4FYPlsJLdX1Hsy4coFHv/aF8rkdSYwp
EflrFfLgBEEZgLvnqfoxh9sPFYKa4amaFL42ouIS2PEVDgzKLk/dzMDeRof0IkIG
yhb4TCS1ArcjS6WsociNGi8ZJN1L3Xctv9WxSkbUYv4Fm2Qyzr8fbSjssjb5NXwD
K11fsj6Pfy/mQrI0TSTlzWC7ARIlCMTWQ8G8zEU6bMFIG6DMjt2J4VgYVXUKetZA
VPuS+pwkH2obQe6FLRuiNxH4GitVAASYPea6foER4AggBMRp8q8F6+WssjoyEORb
0sJxmnxhznoTRMCuTsUj6XMgmOTOnA3lQXsIB0DYcQKBgQDO6mMRVVFWzgkE9Q5/
36n06KvGYF9TCRDL9vRC8kCqcGd1Hy6jRj0D8049KUHaN74pfWg6gsQjPkKzwKnC
vxNl72tVvLqm7Fo531BGfKK/46ZvxeWMMraNW4+9LhwMPu2LN5OEdwwCgyaURpxh
ktCp+RrGjz08Kn82X1jJPdwxDQKBgQDDGMvZ7ZUDGq5+RJkmHJ58lQtiaMZclmYV
R9YwOxJV6ino3EYrGOtUkqiemgAACdMWE/JMJlB1/JINawJwUsZ2XDp/9jNLPgLc
gphCmagaO34U/YMaJbJIK2gkCX7p8EcD+x45qWa0bEMPW38QfN/qQdUPjNmpuIiI
Zleyl1TqDQKBgQCvIoat0ighsAzETGN0aqzhJdrW8xVcJA06hpFi5MdFPBTldno0
KqxUXqj3badWe94SIhqJg8teBUHSAZ3uv2o82nRgQnk99km8OD8rGi1q+9YRP1C2
5OnNJhW4y4FkABNxxZ2v/k+FBNsvn8CXefvyEm3OaMks1s+MBxIQa7KnNQKBgFwX
HUo+GiN/+bPCf6P8yFa4J8qI+HEF0SPkZ9cWWx5QzP2M1FZNie++1nce7DcYbBo0
yh9lyn8W/H328AzDFckS2c5DEY1HtSQPRP3S+AWB5Y7U54h1GMV2L88q6ExWzb60
T10aeE9b9v+NydmniC5UatTPQIMbht8Tp/u18TAVAoGBAJphAfiqWWV2M5aBCSXq
WxLZ71AJ0PZBmRa/9iwtccwXQpMcW6wHK3YSQxci+sB97TElRa3/onlVSpohrUtg
VCvCwfSHX1LmrfWNSkoJZwCQt+YYuMqW86K0tzLzI1EMjIH9LgQvB6RR26PZQs+E
jr1ZvRc+wPTq6sxCF1h9ZAfN
-----END PRIVATE KEY-----
""", #11
]

# To disable the pre-computed tub certs, uncomment this line.
# SYSTEM_TEST_CERTS = []

def flush_but_dont_ignore(res):
    d = flushEventualQueue()
    def _done(ignored):
        return res
    d.addCallback(_done)
    return d

def _render_config(config):
    """
    Convert a ``dict`` of ``dict`` of ``bytes`` to an ini-format string.
    """
    return "\n\n".join(list(
        _render_config_section(k, v)
        for (k, v)
        in config.items()
    ))

def _render_config_section(heading, values):
    """
    Convert a ``bytes`` heading and a ``dict`` of ``bytes`` to an ini-format
    section as ``bytes``.
    """
    return "[{}]\n{}\n".format(
        heading, _render_section_values(values)
    )

def _render_section_values(values):
    """
    Convert a ``dict`` of ``bytes`` to the body of an ini-format section as
    ``bytes``.
    """
    return "\n".join(list(
        "{} = {}".format(k, v)
        for (k, v)
        in sorted(values.items())
    ))


class SystemTestMixin(pollmixin.PollMixin, testutil.StallMixin):

    def setUp(self):
        self.port_assigner = SameProcessStreamEndpointAssigner()
        self.port_assigner.setUp()
        self.addCleanup(self.port_assigner.tearDown)

        self.sparent = service.MultiService()
        self.sparent.startService()

        self.stats_gatherer = None
        self.stats_gatherer_furl = None

    def tearDown(self):
        log.msg("shutting down SystemTest services")
        d = self.sparent.stopService()
        d.addBoth(flush_but_dont_ignore)
        return d

    def getdir(self, subdir):
        return os.path.join(self.basedir, subdir)

    def add_service(self, s):
        s.setServiceParent(self.sparent)
        return s

    def _create_introducer(self):
        """
        :returns: (via Deferred) an Introducer instance
        """
        iv_dir = self.getdir("introducer")
        if not os.path.isdir(iv_dir):
            _, port_endpoint = self.port_assigner.assign(reactor)
            introducer_config = (
                u"[node]\n"
                u"nickname = introducer \N{BLACK SMILING FACE}\n" +
                u"web.port = {}\n".format(port_endpoint)
            ).encode("utf-8")

            fileutil.make_dirs(iv_dir)
            fileutil.write(
                os.path.join(iv_dir, 'tahoe.cfg'),
                introducer_config,
            )
            if SYSTEM_TEST_CERTS:
                os.mkdir(os.path.join(iv_dir, "private"))
                f = open(os.path.join(iv_dir, "private", "node.pem"), "w")
                f.write(SYSTEM_TEST_CERTS[0])
                f.close()
        return create_introducer(basedir=iv_dir)

    def _get_introducer_web(self):
        with open(os.path.join(self.getdir("introducer"), "node.url"), "r") as f:
            return f.read().strip()

    @inlineCallbacks
    def set_up_nodes(self, NUMCLIENTS=5, use_stats_gatherer=False):
        """
        Create an introducer and ``NUMCLIENTS`` client nodes pointed at it.  All
        of the nodes are running in this process.

        As a side-effect, set:

        * ``numclients`` to ``NUMCLIENTS``
        * ``introducer`` to the ``_IntroducerNode`` instance
        * ``introweb_url`` to the introducer's HTTP API endpoint.

        :param int NUMCLIENTS: The number of client nodes to create.

        :param bool use_stats_gatherer: If ``True`` then also create a stats
            gatherer and configure the other nodes to use it.

        :return: A ``Deferred`` that fires when the nodes have connected to
            each other.
        """
        self.numclients = NUMCLIENTS

        self.introducer = yield self._create_introducer()
        self.add_service(self.introducer)
        self.introweb_url = self._get_introducer_web()

        if use_stats_gatherer:
            yield self._set_up_stats_gatherer()
        yield self._set_up_client_nodes()
        if use_stats_gatherer:
            yield self._grab_stats()

    def _set_up_stats_gatherer(self):
        statsdir = self.getdir("stats_gatherer")
        fileutil.make_dirs(statsdir)

        location_hint, port_endpoint = self.port_assigner.assign(reactor)
        fileutil.write(os.path.join(statsdir, "location"), location_hint)
        fileutil.write(os.path.join(statsdir, "port"), port_endpoint)
        self.stats_gatherer_svc = StatsGathererService(statsdir)
        self.stats_gatherer = self.stats_gatherer_svc.stats_gatherer
        self.stats_gatherer_svc.setServiceParent(self.sparent)

        d = fireEventually()
        sgf = os.path.join(statsdir, 'stats_gatherer.furl')
        def check_for_furl():
            return os.path.exists(sgf)
        d.addCallback(lambda junk: self.poll(check_for_furl, timeout=30))
        def get_furl(junk):
            self.stats_gatherer_furl = file(sgf, 'rb').read().strip()
        d.addCallback(get_furl)
        return d

    @inlineCallbacks
    def _set_up_client_nodes(self):
        q = self.introducer
        self.introducer_furl = q.introducer_url
        self.clients = []
        basedirs = []
        for i in range(self.numclients):
            basedirs.append((yield self._set_up_client_node(i)))

        # start clients[0], wait for it's tub to be ready (at which point it
        # will have registered the helper furl).
        c = yield client.create_client(basedirs[0])
        c.setServiceParent(self.sparent)
        self.clients.append(c)
        c.set_default_mutable_keysize(TEST_RSA_KEY_SIZE)

        with open(os.path.join(basedirs[0],"private","helper.furl"), "r") as f:
            helper_furl = f.read()

        self.helper_furl = helper_furl
        if self.numclients >= 4:
            with open(os.path.join(basedirs[3], 'tahoe.cfg'), 'ab+') as f:
                f.write(
                    "[client]\n"
                    "helper.furl = {}\n".format(helper_furl)
                )

        # this starts the rest of the clients
        for i in range(1, self.numclients):
            c = yield client.create_client(basedirs[i])
            c.setServiceParent(self.sparent)
            self.clients.append(c)
            c.set_default_mutable_keysize(TEST_RSA_KEY_SIZE)
        log.msg("STARTING")
        yield self.wait_for_connections()
        log.msg("CONNECTED")
        # now find out where the web port was
        self.webish_url = self.clients[0].getServiceNamed("webish").getURL()
        if self.numclients >=4:
            # and the helper-using webport
            self.helper_webish_url = self.clients[3].getServiceNamed("webish").getURL()

    def _generate_config(self, which, basedir):
        config = {}

        except1 = set(range(self.numclients)) - {1}
        feature_matrix = {
            # client 1 uses private/introducers.yaml, not tahoe.cfg
            ("client", "introducer.furl"): except1,
            ("client", "nickname"): except1,

            # client 1 has to auto-assign an address.
            ("node", "tub.port"): except1,
            ("node", "tub.location"): except1,

            # client 0 runs a webserver and a helper
            # client 3 runs a webserver but no helper
            ("node", "web.port"): {0, 3},
            ("node", "timeout.keepalive"): {0},
            ("node", "timeout.disconnect"): {3},

            ("helper", "enabled"): {0},
        }

        def setconf(config, which, section, feature, value):
            if which in feature_matrix.get((section, feature), {which}):
                if isinstance(value, unicode):
                    value = value.encode("utf-8")
                config.setdefault(section, {})[feature] = value

        setclient = partial(setconf, config, which, "client")
        setnode = partial(setconf, config, which, "node")
        sethelper = partial(setconf, config, which, "helper")

        setclient("introducer.furl", self.introducer_furl)
        setnode("nickname", u"client %d \N{BLACK SMILING FACE}" % (which,))

        if self.stats_gatherer_furl:
            setclient("stats_gatherer.furl", self.stats_gatherer_furl)

        tub_location_hint, tub_port_endpoint = self.port_assigner.assign(reactor)
        setnode("tub.port", tub_port_endpoint)
        setnode("tub.location", tub_location_hint)

        _, web_port_endpoint = self.port_assigner.assign(reactor)
        setnode("web.port", web_port_endpoint)
        setnode("timeout.keepalive", "600")
        setnode("timeout.disconnect", "1800")

        sethelper("enabled", "True")

        if which == 1:
            # clients[1] uses private/introducers.yaml, not tahoe.cfg
            iyaml = ("introducers:\n"
                     " petname2:\n"
                     "  furl: %s\n") % self.introducer_furl
            iyaml_fn = os.path.join(basedir, "private", "introducers.yaml")
            fileutil.write(iyaml_fn, iyaml)

        return _render_config(config)

    def _set_up_client_node(self, which):
        basedir = self.getdir("client%d" % (which,))
        fileutil.make_dirs(os.path.join(basedir, "private"))
        if len(SYSTEM_TEST_CERTS) > (which + 1):
            f = open(os.path.join(basedir, "private", "node.pem"), "w")
            f.write(SYSTEM_TEST_CERTS[which + 1])
            f.close()
        config = self._generate_config(which, basedir)
        fileutil.write(os.path.join(basedir, 'tahoe.cfg'), config)
        return basedir

    def _grab_stats(self):
        d = self.stats_gatherer.poll()
        return d

    def bounce_client(self, num):
        c = self.clients[num]
        d = c.disownServiceParent()
        # I think windows requires a moment to let the connection really stop
        # and the port number made available for re-use. TODO: examine the
        # behavior, see if this is really the problem, see if we can do
        # better than blindly waiting for a second.
        d.addCallback(self.stall, 1.0)

        @defer.inlineCallbacks
        def _stopped(res):
            new_c = yield client.create_client(self.getdir("client%d" % num))
            self.clients[num] = new_c
            new_c.set_default_mutable_keysize(TEST_RSA_KEY_SIZE)
            new_c.setServiceParent(self.sparent)
        d.addCallback(_stopped)
        d.addCallback(lambda res: self.wait_for_connections())
        def _maybe_get_webport(res):
            if num == 0:
                # now find out where the web port was
                self.webish_url = self.clients[0].getServiceNamed("webish").getURL()
        d.addCallback(_maybe_get_webport)
        return d

    @defer.inlineCallbacks
    def add_extra_node(self, client_num, helper_furl=None,
                       add_to_sparent=False):
        # usually this node is *not* parented to our self.sparent, so we can
        # shut it down separately from the rest, to exercise the
        # connection-lost code
        basedir = self.getdir("client%d" % client_num)
        if not os.path.isdir(basedir):
            fileutil.make_dirs(basedir)
        config = "[client]\n"
        config += "introducer.furl = %s\n" % self.introducer_furl
        if helper_furl:
            config += "helper.furl = %s\n" % helper_furl
        fileutil.write(os.path.join(basedir, 'tahoe.cfg'), config)

        c = yield client.create_client(basedir)
        self.clients.append(c)
        c.set_default_mutable_keysize(TEST_RSA_KEY_SIZE)
        self.numclients += 1
        if add_to_sparent:
            c.setServiceParent(self.sparent)
        else:
            c.startService()
        yield self.wait_for_connections()
        defer.returnValue(c)

    def _check_connections(self):
        for i, c in enumerate(self.clients):
            if not c.connected_to_introducer():
                log.msg("%s not connected to introducer yet" % (i,))
                return False
            sb = c.get_storage_broker()
            connected_servers = sb.get_connected_servers()
            connected_names = sorted(list(
                connected.get_nickname()
                for connected
                in sb.get_known_servers()
                if connected.is_connected()
            ))
            if len(connected_servers) != self.numclients:
                wanted = sorted(list(
                    client.nickname
                    for client
                    in self.clients
                ))
                log.msg(
                    "client %s storage broker connected to %s, missing %s" % (
                        i,
                        connected_names,
                        set(wanted) - set(connected_names),
                    )
                )
                return False
            log.msg("client %s storage broker connected to %s, happy" % (
                i, connected_names,
            ))
            up = c.getServiceNamed("uploader")
            if up._helper_furl and not up._helper:
                log.msg("Helper fURL but no helper")
                return False
        return True

    def wait_for_connections(self, ignored=None):
        return self.poll(self._check_connections, timeout=200)

class CountingDataUploadable(upload.Data):
    bytes_read = 0
    interrupt_after = None
    interrupt_after_d = None

    def read(self, length):
        self.bytes_read += length
        if self.interrupt_after is not None:
            if self.bytes_read > self.interrupt_after:
                self.interrupt_after = None
                self.interrupt_after_d.callback(self)
        return upload.Data.read(self, length)

class SystemTest(SystemTestMixin, RunBinTahoeMixin, unittest.TestCase):

    timeout = 180

    def test_connections(self):
        self.basedir = "system/SystemTest/test_connections"
        d = self.set_up_nodes()
        self.extra_node = None
        d.addCallback(lambda res: self.add_extra_node(self.numclients))
        def _check(extra_node):
            self.extra_node = extra_node
            for c in self.clients:
                all_peerids = c.get_storage_broker().get_all_serverids()
                self.failUnlessEqual(len(all_peerids), self.numclients+1)
                sb = c.storage_broker
                permuted_peers = sb.get_servers_for_psi("a")
                self.failUnlessEqual(len(permuted_peers), self.numclients+1)

        d.addCallback(_check)
        def _shutdown_extra_node(res):
            if self.extra_node:
                return self.extra_node.stopService()
            return res
        d.addBoth(_shutdown_extra_node)
        return d
    # test_connections is subsumed by test_upload_and_download, and takes
    # quite a while to run on a slow machine (because of all the TLS
    # connections that must be established). If we ever rework the introducer
    # code to such an extent that we're not sure if it works anymore, we can
    # reinstate this test until it does.
    del test_connections

    def test_upload_and_download_random_key(self):
        self.basedir = "system/SystemTest/test_upload_and_download_random_key"
        return self._test_upload_and_download(convergence=None)

    def test_upload_and_download_convergent(self):
        self.basedir = "system/SystemTest/test_upload_and_download_convergent"
        return self._test_upload_and_download(convergence="some convergence string")

    def _test_upload_and_download(self, convergence):
        # we use 4000 bytes of data, which will result in about 400k written
        # to disk among all our simulated nodes
        DATA = "Some data to upload\n" * 200
        d = self.set_up_nodes()
        def _check_connections(res):
            for c in self.clients:
                c.encoding_params['happy'] = 5
                all_peerids = c.get_storage_broker().get_all_serverids()
                self.failUnlessEqual(len(all_peerids), self.numclients)
                sb = c.storage_broker
                permuted_peers = sb.get_servers_for_psi("a")
                self.failUnlessEqual(len(permuted_peers), self.numclients)
        d.addCallback(_check_connections)

        def _do_upload(res):
            log.msg("UPLOADING")
            u = self.clients[0].getServiceNamed("uploader")
            self.uploader = u
            # we crank the max segsize down to 1024b for the duration of this
            # test, so we can exercise multiple segments. It is important
            # that this is not a multiple of the segment size, so that the
            # tail segment is not the same length as the others. This actualy
            # gets rounded up to 1025 to be a multiple of the number of
            # required shares (since we use 25 out of 100 FEC).
            up = upload.Data(DATA, convergence=convergence)
            up.max_segment_size = 1024
            d1 = u.upload(up)
            return d1
        d.addCallback(_do_upload)
        def _upload_done(results):
            theuri = results.get_uri()
            log.msg("upload finished: uri is %s" % (theuri,))
            self.uri = theuri
            assert isinstance(self.uri, str), self.uri
            self.cap = uri.from_string(self.uri)
            self.n = self.clients[1].create_node_from_uri(self.uri)
        d.addCallback(_upload_done)

        def _upload_again(res):
            # Upload again. If using convergent encryption then this ought to be
            # short-circuited, however with the way we currently generate URIs
            # (i.e. because they include the roothash), we have to do all of the
            # encoding work, and only get to save on the upload part.
            log.msg("UPLOADING AGAIN")
            up = upload.Data(DATA, convergence=convergence)
            up.max_segment_size = 1024
            return self.uploader.upload(up)
        d.addCallback(_upload_again)

        def _download_to_data(res):
            log.msg("DOWNLOADING")
            return download_to_data(self.n)
        d.addCallback(_download_to_data)
        def _download_to_data_done(data):
            log.msg("download finished")
            self.failUnlessEqual(data, DATA)
        d.addCallback(_download_to_data_done)

        def _test_read(res):
            n = self.clients[1].create_node_from_uri(self.uri)
            d = download_to_data(n)
            def _read_done(data):
                self.failUnlessEqual(data, DATA)
            d.addCallback(_read_done)
            d.addCallback(lambda ign:
                          n.read(MemoryConsumer(), offset=1, size=4))
            def _read_portion_done(mc):
                self.failUnlessEqual("".join(mc.chunks), DATA[1:1+4])
            d.addCallback(_read_portion_done)
            d.addCallback(lambda ign:
                          n.read(MemoryConsumer(), offset=2, size=None))
            def _read_tail_done(mc):
                self.failUnlessEqual("".join(mc.chunks), DATA[2:])
            d.addCallback(_read_tail_done)
            d.addCallback(lambda ign:
                          n.read(MemoryConsumer(), size=len(DATA)+1000))
            def _read_too_much(mc):
                self.failUnlessEqual("".join(mc.chunks), DATA)
            d.addCallback(_read_too_much)

            return d
        d.addCallback(_test_read)

        def _test_bad_read(res):
            bad_u = uri.from_string_filenode(self.uri)
            bad_u.key = self.flip_bit(bad_u.key)
            bad_n = self.clients[1].create_node_from_uri(bad_u.to_string())
            # this should cause an error during download

            d = self.shouldFail2(NoSharesError, "'download bad node'",
                                 None,
                                 bad_n.read, MemoryConsumer(), offset=2)
            return d
        d.addCallback(_test_bad_read)

        def _download_nonexistent_uri(res):
            baduri = self.mangle_uri(self.uri)
            badnode = self.clients[1].create_node_from_uri(baduri)
            log.msg("about to download non-existent URI", level=log.UNUSUAL,
                    facility="tahoe.tests")
            d1 = download_to_data(badnode)
            def _baduri_should_fail(res):
                log.msg("finished downloading non-existent URI",
                        level=log.UNUSUAL, facility="tahoe.tests")
                self.failUnless(isinstance(res, Failure))
                self.failUnless(res.check(NoSharesError),
                                "expected NoSharesError, got %s" % res)
            d1.addBoth(_baduri_should_fail)
            return d1
        d.addCallback(_download_nonexistent_uri)

        # add a new node, which doesn't accept shares, and only uses the
        # helper for upload.
        d.addCallback(lambda res: self.add_extra_node(self.numclients,
                                                      self.helper_furl,
                                                      add_to_sparent=True))
        def _added(extra_node):
            self.extra_node = extra_node
            self.extra_node.encoding_params['happy'] = 5
        d.addCallback(_added)

        def _has_helper():
            uploader = self.extra_node.getServiceNamed("uploader")
            furl, connected = uploader.get_helper_info()
            return connected
        d.addCallback(lambda ign: self.poll(_has_helper))

        HELPER_DATA = "Data that needs help to upload" * 1000
        def _upload_with_helper(res):
            u = upload.Data(HELPER_DATA, convergence=convergence)
            d = self.extra_node.upload(u)
            def _uploaded(results):
                n = self.clients[1].create_node_from_uri(results.get_uri())
                return download_to_data(n)
            d.addCallback(_uploaded)
            def _check(newdata):
                self.failUnlessEqual(newdata, HELPER_DATA)
            d.addCallback(_check)
            return d
        d.addCallback(_upload_with_helper)

        def _upload_duplicate_with_helper(res):
            u = upload.Data(HELPER_DATA, convergence=convergence)
            u.debug_stash_RemoteEncryptedUploadable = True
            d = self.extra_node.upload(u)
            def _uploaded(results):
                n = self.clients[1].create_node_from_uri(results.get_uri())
                return download_to_data(n)
            d.addCallback(_uploaded)
            def _check(newdata):
                self.failUnlessEqual(newdata, HELPER_DATA)
                self.failIf(hasattr(u, "debug_RemoteEncryptedUploadable"),
                            "uploadable started uploading, should have been avoided")
            d.addCallback(_check)
            return d
        if convergence is not None:
            d.addCallback(_upload_duplicate_with_helper)

        d.addCallback(fireEventually)

        def _upload_resumable(res):
            DATA = "Data that needs help to upload and gets interrupted" * 1000
            u1 = CountingDataUploadable(DATA, convergence=convergence)
            u2 = CountingDataUploadable(DATA, convergence=convergence)

            # we interrupt the connection after about 5kB by shutting down
            # the helper, then restarting it.
            u1.interrupt_after = 5000
            u1.interrupt_after_d = defer.Deferred()
            bounced_d = defer.Deferred()
            def _do_bounce(res):
                d = self.bounce_client(0)
                d.addBoth(bounced_d.callback)
            u1.interrupt_after_d.addCallback(_do_bounce)

            # sneak into the helper and reduce its chunk size, so that our
            # debug_interrupt will sever the connection on about the fifth
            # chunk fetched. This makes sure that we've started to write the
            # new shares before we abandon them, which exercises the
            # abort/delete-partial-share code. TODO: find a cleaner way to do
            # this. I know that this will affect later uses of the helper in
            # this same test run, but I'm not currently worried about it.
            offloaded.CHKCiphertextFetcher.CHUNK_SIZE = 1000

            upload_d = self.extra_node.upload(u1)
            # The upload will start, and bounce_client() will be called after
            # about 5kB. bounced_d will fire after bounce_client() finishes
            # shutting down and restarting the node.
            d = bounced_d
            def _bounced(ign):
                # By this point, the upload should have failed because of the
                # interruption. upload_d will fire in a moment
                def _should_not_finish(res):
                    self.fail("interrupted upload should have failed, not"
                              " finished with result %s" % (res,))
                def _interrupted(f):
                    f.trap(DeadReferenceError)
                    # make sure we actually interrupted it before finishing
                    # the file
                    self.failUnless(u1.bytes_read < len(DATA),
                                    "read %d out of %d total" %
                                    (u1.bytes_read, len(DATA)))
                upload_d.addCallbacks(_should_not_finish, _interrupted)
                return upload_d
            d.addCallback(_bounced)

            def _disconnected(res):
                # check to make sure the storage servers aren't still hanging
                # on to the partial share: their incoming/ directories should
                # now be empty.
                log.msg("disconnected", level=log.NOISY,
                        facility="tahoe.test.test_system")
                for i in range(self.numclients):
                    incdir = os.path.join(self.getdir("client%d" % i),
                                          "storage", "shares", "incoming")
                    self.failIf(os.path.exists(incdir) and os.listdir(incdir))
            d.addCallback(_disconnected)

            d.addCallback(lambda res:
                          log.msg("wait_for_helper", level=log.NOISY,
                                  facility="tahoe.test.test_system"))
            # then we need to wait for the extra node to reestablish its
            # connection to the helper.
            d.addCallback(lambda ign: self.poll(_has_helper))

            d.addCallback(lambda res:
                          log.msg("uploading again", level=log.NOISY,
                                  facility="tahoe.test.test_system"))
            d.addCallback(lambda res: self.extra_node.upload(u2))

            def _uploaded(results):
                cap = results.get_uri()
                log.msg("Second upload complete", level=log.NOISY,
                        facility="tahoe.test.test_system")

                # this is really bytes received rather than sent, but it's
                # convenient and basically measures the same thing
                bytes_sent = results.get_ciphertext_fetched()
                self.failUnless(isinstance(bytes_sent, int), bytes_sent)

                # We currently don't support resumption of upload if the data is
                # encrypted with a random key.  (Because that would require us
                # to store the key locally and re-use it on the next upload of
                # this file, which isn't a bad thing to do, but we currently
                # don't do it.)
                if convergence is not None:
                    # Make sure we did not have to read the whole file the
                    # second time around .
                    self.failUnless(bytes_sent < len(DATA),
                                    "resumption didn't save us any work:"
                                    " read %r bytes out of %r total" %
                                    (bytes_sent, len(DATA)))
                else:
                    # Make sure we did have to read the whole file the second
                    # time around -- because the one that we partially uploaded
                    # earlier was encrypted with a different random key.
                    self.failIf(bytes_sent < len(DATA),
                                "resumption saved us some work even though we were using random keys:"
                                " read %r bytes out of %r total" %
                                (bytes_sent, len(DATA)))
                n = self.clients[1].create_node_from_uri(cap)
                return download_to_data(n)
            d.addCallback(_uploaded)

            def _check(newdata):
                self.failUnlessEqual(newdata, DATA)
                # If using convergent encryption, then also check that the
                # helper has removed the temp file from its directories.
                if convergence is not None:
                    basedir = os.path.join(self.getdir("client0"), "helper")
                    files = os.listdir(os.path.join(basedir, "CHK_encoding"))
                    self.failUnlessEqual(files, [])
                    files = os.listdir(os.path.join(basedir, "CHK_incoming"))
                    self.failUnlessEqual(files, [])
            d.addCallback(_check)
            return d
        d.addCallback(_upload_resumable)

        def _grab_stats(ignored):
            # the StatsProvider doesn't normally publish a FURL:
            # instead it passes a live reference to the StatsGatherer
            # (if and when it connects). To exercise the remote stats
            # interface, we manually publish client0's StatsProvider
            # and use client1 to query it.
            sp = self.clients[0].stats_provider
            sp_furl = self.clients[0].tub.registerReference(sp)
            d = self.clients[1].tub.getReference(sp_furl)
            d.addCallback(lambda sp_rref: sp_rref.callRemote("get_stats"))
            def _got_stats(stats):
                #print("STATS")
                #from pprint import pprint
                #pprint(stats)
                s = stats["stats"]
                self.failUnlessEqual(s["storage_server.accepting_immutable_shares"], 1)
                c = stats["counters"]
                self.failUnless("storage_server.allocate" in c)
            d.addCallback(_got_stats)
            return d
        d.addCallback(_grab_stats)

        return d

    def _find_all_shares(self, basedir):
        shares = []
        for (dirpath, dirnames, filenames) in os.walk(basedir):
            if "storage" not in dirpath:
                continue
            if not filenames:
                continue
            pieces = dirpath.split(os.sep)
            if (len(pieces) >= 5
                and pieces[-4] == "storage"
                and pieces[-3] == "shares"):
                # we're sitting in .../storage/shares/$START/$SINDEX , and there
                # are sharefiles here
                assert pieces[-5].startswith("client")
                client_num = int(pieces[-5][-1])
                storage_index_s = pieces[-1]
                storage_index = si_a2b(storage_index_s)
                for sharename in filenames:
                    shnum = int(sharename)
                    filename = os.path.join(dirpath, sharename)
                    data = (client_num, storage_index, filename, shnum)
                    shares.append(data)
        if not shares:
            self.fail("unable to find any share files in %s" % basedir)
        return shares

    def _corrupt_mutable_share(self, filename, which):
        msf = MutableShareFile(filename)
        datav = msf.readv([ (0, 1000000) ])
        final_share = datav[0]
        assert len(final_share) < 1000000 # ought to be truncated
        pieces = mutable_layout.unpack_share(final_share)
        (seqnum, root_hash, IV, k, N, segsize, datalen,
         verification_key, signature, share_hash_chain, block_hash_tree,
         share_data, enc_privkey) = pieces

        if which == "seqnum":
            seqnum = seqnum + 15
        elif which == "R":
            root_hash = self.flip_bit(root_hash)
        elif which == "IV":
            IV = self.flip_bit(IV)
        elif which == "segsize":
            segsize = segsize + 15
        elif which == "pubkey":
            verification_key = self.flip_bit(verification_key)
        elif which == "signature":
            signature = self.flip_bit(signature)
        elif which == "share_hash_chain":
            nodenum = share_hash_chain.keys()[0]
            share_hash_chain[nodenum] = self.flip_bit(share_hash_chain[nodenum])
        elif which == "block_hash_tree":
            block_hash_tree[-1] = self.flip_bit(block_hash_tree[-1])
        elif which == "share_data":
            share_data = self.flip_bit(share_data)
        elif which == "encprivkey":
            enc_privkey = self.flip_bit(enc_privkey)

        prefix = mutable_layout.pack_prefix(seqnum, root_hash, IV, k, N,
                                            segsize, datalen)
        final_share = mutable_layout.pack_share(prefix,
                                                verification_key,
                                                signature,
                                                share_hash_chain,
                                                block_hash_tree,
                                                share_data,
                                                enc_privkey)
        msf.writev( [(0, final_share)], None)


    def test_mutable(self):
        self.basedir = "system/SystemTest/test_mutable"
        DATA = "initial contents go here."  # 25 bytes % 3 != 0
        DATA_uploadable = MutableData(DATA)
        NEWDATA = "new contents yay"
        NEWDATA_uploadable = MutableData(NEWDATA)
        NEWERDATA = "this is getting old"
        NEWERDATA_uploadable = MutableData(NEWERDATA)

        d = self.set_up_nodes()

        def _create_mutable(res):
            c = self.clients[0]
            log.msg("starting create_mutable_file")
            d1 = c.create_mutable_file(DATA_uploadable)
            def _done(res):
                log.msg("DONE: %s" % (res,))
                self._mutable_node_1 = res
            d1.addCallback(_done)
            return d1
        d.addCallback(_create_mutable)

        @defer.inlineCallbacks
        def _test_debug(res):
            # find a share. It is important to run this while there is only
            # one slot in the grid.
            shares = self._find_all_shares(self.basedir)
            (client_num, storage_index, filename, shnum) = shares[0]
            log.msg("test_system.SystemTest.test_mutable._test_debug using %s"
                    % filename)
            log.msg(" for clients[%d]" % client_num)

            rc,output,err = yield run_cli("debug", "dump-share", "--offsets",
                                          filename)
            self.failUnlessEqual(rc, 0)
            try:
                self.failUnless("Mutable slot found:\n" in output)
                self.failUnless("share_type: SDMF\n" in output)
                peerid = idlib.nodeid_b2a(self.clients[client_num].nodeid)
                self.failUnless(" WE for nodeid: %s\n" % peerid in output)
                self.failUnless(" num_extra_leases: 0\n" in output)
                self.failUnless("  secrets are for nodeid: %s\n" % peerid
                                in output)
                self.failUnless(" SDMF contents:\n" in output)
                self.failUnless("  seqnum: 1\n" in output)
                self.failUnless("  required_shares: 3\n" in output)
                self.failUnless("  total_shares: 10\n" in output)
                self.failUnless("  segsize: 27\n" in output, (output, filename))
                self.failUnless("  datalen: 25\n" in output)
                # the exact share_hash_chain nodes depends upon the sharenum,
                # and is more of a hassle to compute than I want to deal with
                # now
                self.failUnless("  share_hash_chain: " in output)
                self.failUnless("  block_hash_tree: 1 nodes\n" in output)
                expected = ("  verify-cap: URI:SSK-Verifier:%s:" %
                            base32.b2a(storage_index))
                self.failUnless(expected in output)
            except unittest.FailTest:
                print()
                print("dump-share output was:")
                print(output)
                raise
        d.addCallback(_test_debug)

        # test retrieval

        # first, let's see if we can use the existing node to retrieve the
        # contents. This allows it to use the cached pubkey and maybe the
        # latest-known sharemap.

        d.addCallback(lambda res: self._mutable_node_1.download_best_version())
        def _check_download_1(res):
            self.failUnlessEqual(res, DATA)
            # now we see if we can retrieve the data from a new node,
            # constructed using the URI of the original one. We do this test
            # on the same client that uploaded the data.
            uri = self._mutable_node_1.get_uri()
            log.msg("starting retrieve1")
            newnode = self.clients[0].create_node_from_uri(uri)
            newnode_2 = self.clients[0].create_node_from_uri(uri)
            self.failUnlessIdentical(newnode, newnode_2)
            return newnode.download_best_version()
        d.addCallback(_check_download_1)

        def _check_download_2(res):
            self.failUnlessEqual(res, DATA)
            # same thing, but with a different client
            uri = self._mutable_node_1.get_uri()
            newnode = self.clients[1].create_node_from_uri(uri)
            log.msg("starting retrieve2")
            d1 = newnode.download_best_version()
            d1.addCallback(lambda res: (res, newnode))
            return d1
        d.addCallback(_check_download_2)

        def _check_download_3(res_and_newnode):
            (res, newnode) = res_and_newnode
            self.failUnlessEqual(res, DATA)
            # replace the data
            log.msg("starting replace1")
            d1 = newnode.overwrite(NEWDATA_uploadable)
            d1.addCallback(lambda res: newnode.download_best_version())
            return d1
        d.addCallback(_check_download_3)

        def _check_download_4(res):
            self.failUnlessEqual(res, NEWDATA)
            # now create an even newer node and replace the data on it. This
            # new node has never been used for download before.
            uri = self._mutable_node_1.get_uri()
            newnode1 = self.clients[2].create_node_from_uri(uri)
            newnode2 = self.clients[3].create_node_from_uri(uri)
            self._newnode3 = self.clients[3].create_node_from_uri(uri)
            log.msg("starting replace2")
            d1 = newnode1.overwrite(NEWERDATA_uploadable)
            d1.addCallback(lambda res: newnode2.download_best_version())
            return d1
        d.addCallback(_check_download_4)

        def _check_download_5(res):
            log.msg("finished replace2")
            self.failUnlessEqual(res, NEWERDATA)
        d.addCallback(_check_download_5)

        def _corrupt_shares(res):
            # run around and flip bits in all but k of the shares, to test
            # the hash checks
            shares = self._find_all_shares(self.basedir)
            ## sort by share number
            #shares.sort( lambda a,b: cmp(a[3], b[3]) )
            where = dict([ (shnum, filename)
                           for (client_num, storage_index, filename, shnum)
                           in shares ])
            assert len(where) == 10 # this test is designed for 3-of-10
            for shnum, filename in where.items():
                # shares 7,8,9 are left alone. read will check
                # (share_hash_chain, block_hash_tree, share_data). New
                # seqnum+R pairs will trigger a check of (seqnum, R, IV,
                # segsize, signature).
                if shnum == 0:
                    # read: this will trigger "pubkey doesn't match
                    # fingerprint".
                    self._corrupt_mutable_share(filename, "pubkey")
                    self._corrupt_mutable_share(filename, "encprivkey")
                elif shnum == 1:
                    # triggers "signature is invalid"
                    self._corrupt_mutable_share(filename, "seqnum")
                elif shnum == 2:
                    # triggers "signature is invalid"
                    self._corrupt_mutable_share(filename, "R")
                elif shnum == 3:
                    # triggers "signature is invalid"
                    self._corrupt_mutable_share(filename, "segsize")
                elif shnum == 4:
                    self._corrupt_mutable_share(filename, "share_hash_chain")
                elif shnum == 5:
                    self._corrupt_mutable_share(filename, "block_hash_tree")
                elif shnum == 6:
                    self._corrupt_mutable_share(filename, "share_data")
                # other things to correct: IV, signature
                # 7,8,9 are left alone

                # note that initial_query_count=5 means that we'll hit the
                # first 5 servers in effectively random order (based upon
                # response time), so we won't necessarily ever get a "pubkey
                # doesn't match fingerprint" error (if we hit shnum>=1 before
                # shnum=0, we pull the pubkey from there). To get repeatable
                # specific failures, we need to set initial_query_count=1,
                # but of course that will change the sequencing behavior of
                # the retrieval process. TODO: find a reasonable way to make
                # this a parameter, probably when we expand this test to test
                # for one failure mode at a time.

                # when we retrieve this, we should get three signature
                # failures (where we've mangled seqnum, R, and segsize). The
                # pubkey mangling
        d.addCallback(_corrupt_shares)

        d.addCallback(lambda res: self._newnode3.download_best_version())
        d.addCallback(_check_download_5)

        def _check_empty_file(res):
            # make sure we can create empty files, this usually screws up the
            # segsize math
            d1 = self.clients[2].create_mutable_file(MutableData(""))
            d1.addCallback(lambda newnode: newnode.download_best_version())
            d1.addCallback(lambda res: self.failUnlessEqual("", res))
            return d1
        d.addCallback(_check_empty_file)

        d.addCallback(lambda res: self.clients[0].create_dirnode())
        def _created_dirnode(dnode):
            log.msg("_created_dirnode(%s)" % (dnode,))
            d1 = dnode.list()
            d1.addCallback(lambda children: self.failUnlessEqual(children, {}))
            d1.addCallback(lambda res: dnode.has_child(u"edgar"))
            d1.addCallback(lambda answer: self.failUnlessEqual(answer, False))
            d1.addCallback(lambda res: dnode.set_node(u"see recursive", dnode))
            d1.addCallback(lambda res: dnode.has_child(u"see recursive"))
            d1.addCallback(lambda answer: self.failUnlessEqual(answer, True))
            d1.addCallback(lambda res: dnode.build_manifest().when_done())
            d1.addCallback(lambda res:
                           self.failUnlessEqual(len(res["manifest"]), 1))
            return d1
        d.addCallback(_created_dirnode)

        return d

    def flip_bit(self, good):
        return good[:-1] + chr(ord(good[-1]) ^ 0x01)

    def mangle_uri(self, gooduri):
        # change the key, which changes the storage index, which means we'll
        # be asking about the wrong file, so nobody will have any shares
        u = uri.from_string(gooduri)
        u2 = uri.CHKFileURI(key=self.flip_bit(u.key),
                            uri_extension_hash=u.uri_extension_hash,
                            needed_shares=u.needed_shares,
                            total_shares=u.total_shares,
                            size=u.size)
        return u2.to_string()

    # TODO: add a test which mangles the uri_extension_hash instead, and
    # should fail due to not being able to get a valid uri_extension block.
    # Also a test which sneakily mangles the uri_extension block to change
    # some of the validation data, so it will fail in the post-download phase
    # when the file's crypttext integrity check fails. Do the same thing for
    # the key, which should cause the download to fail the post-download
    # plaintext_hash check.

    def test_filesystem(self):
        self.basedir = "system/SystemTest/test_filesystem"
        self.data = LARGE_DATA
        d = self.set_up_nodes(use_stats_gatherer=True)
        def _new_happy_semantics(ign):
            for c in self.clients:
                c.encoding_params['happy'] = 1
        d.addCallback(_new_happy_semantics)
        d.addCallback(self.log, "starting publish")
        d.addCallback(self._do_publish1)
        d.addCallback(self._test_runner)
        d.addCallback(self._do_publish2)
        # at this point, we have the following filesystem (where "R" denotes
        # self._root_directory_uri):
        # R
        # R/subdir1
        # R/subdir1/mydata567
        # R/subdir1/subdir2/
        # R/subdir1/subdir2/mydata992

        d.addCallback(lambda res: self.bounce_client(0))
        d.addCallback(self.log, "bounced client0")

        d.addCallback(self._check_publish1)
        d.addCallback(self.log, "did _check_publish1")
        d.addCallback(self._check_publish2)
        d.addCallback(self.log, "did _check_publish2")
        d.addCallback(self._do_publish_private)
        d.addCallback(self.log, "did _do_publish_private")
        # now we also have (where "P" denotes a new dir):
        #  P/personal/sekrit data
        #  P/s2-rw -> /subdir1/subdir2/
        #  P/s2-ro -> /subdir1/subdir2/ (read-only)
        d.addCallback(self._check_publish_private)
        d.addCallback(self.log, "did _check_publish_private")
        d.addCallback(self._test_web)
        d.addCallback(self._test_control)
        d.addCallback(self._test_cli)
        # P now has four top-level children:
        # P/personal/sekrit data
        # P/s2-ro/
        # P/s2-rw/
        # P/test_put/  (empty)
        d.addCallback(self._test_checker)
        return d

    def _do_publish1(self, res):
        ut = upload.Data(self.data, convergence=None)
        c0 = self.clients[0]
        d = c0.create_dirnode()
        def _made_root(new_dirnode):
            self._root_directory_uri = new_dirnode.get_uri()
            return c0.create_node_from_uri(self._root_directory_uri)
        d.addCallback(_made_root)
        d.addCallback(lambda root: root.create_subdirectory(u"subdir1"))
        def _made_subdir1(subdir1_node):
            self._subdir1_node = subdir1_node
            d1 = subdir1_node.add_file(u"mydata567", ut)
            d1.addCallback(self.log, "publish finished")
            def _stash_uri(filenode):
                self.uri = filenode.get_uri()
                assert isinstance(self.uri, str), (self.uri, filenode)
            d1.addCallback(_stash_uri)
            return d1
        d.addCallback(_made_subdir1)
        return d

    def _do_publish2(self, res):
        ut = upload.Data(self.data, convergence=None)
        d = self._subdir1_node.create_subdirectory(u"subdir2")
        d.addCallback(lambda subdir2: subdir2.add_file(u"mydata992", ut))
        return d

    def log(self, res, *args, **kwargs):
        # print("MSG: %s  RES: %s" % (msg, args))
        log.msg(*args, **kwargs)
        return res

    def _do_publish_private(self, res):
        self.smalldata = "sssh, very secret stuff"
        ut = upload.Data(self.smalldata, convergence=None)
        d = self.clients[0].create_dirnode()
        d.addCallback(self.log, "GOT private directory")
        def _got_new_dir(privnode):
            rootnode = self.clients[0].create_node_from_uri(self._root_directory_uri)
            d1 = privnode.create_subdirectory(u"personal")
            d1.addCallback(self.log, "made P/personal")
            d1.addCallback(lambda node: node.add_file(u"sekrit data", ut))
            d1.addCallback(self.log, "made P/personal/sekrit data")
            d1.addCallback(lambda res: rootnode.get_child_at_path([u"subdir1", u"subdir2"]))
            def _got_s2(s2node):
                d2 = privnode.set_uri(u"s2-rw", s2node.get_uri(),
                                      s2node.get_readonly_uri())
                d2.addCallback(lambda node:
                               privnode.set_uri(u"s2-ro",
                                                s2node.get_readonly_uri(),
                                                s2node.get_readonly_uri()))
                return d2
            d1.addCallback(_got_s2)
            d1.addCallback(lambda res: privnode)
            return d1
        d.addCallback(_got_new_dir)
        return d

    def _check_publish1(self, res):
        # this one uses the iterative API
        c1 = self.clients[1]
        d = defer.succeed(c1.create_node_from_uri(self._root_directory_uri))
        d.addCallback(self.log, "check_publish1 got /")
        d.addCallback(lambda root: root.get(u"subdir1"))
        d.addCallback(lambda subdir1: subdir1.get(u"mydata567"))
        d.addCallback(lambda filenode: download_to_data(filenode))
        d.addCallback(self.log, "get finished")
        def _get_done(data):
            self.failUnlessEqual(data, self.data)
        d.addCallback(_get_done)
        return d

    def _check_publish2(self, res):
        # this one uses the path-based API
        rootnode = self.clients[1].create_node_from_uri(self._root_directory_uri)
        d = rootnode.get_child_at_path(u"subdir1")
        d.addCallback(lambda dirnode:
                      self.failUnless(IDirectoryNode.providedBy(dirnode)))
        d.addCallback(lambda res: rootnode.get_child_at_path(u"subdir1/mydata567"))
        d.addCallback(lambda filenode: download_to_data(filenode))
        d.addCallback(lambda data: self.failUnlessEqual(data, self.data))

        d.addCallback(lambda res: rootnode.get_child_at_path(u"subdir1/mydata567"))
        def _got_filenode(filenode):
            fnode = self.clients[1].create_node_from_uri(filenode.get_uri())
            assert fnode == filenode
        d.addCallback(_got_filenode)
        return d

    def _check_publish_private(self, resnode):
        # this one uses the path-based API
        self._private_node = resnode

        d = self._private_node.get_child_at_path(u"personal")
        def _got_personal(personal):
            self._personal_node = personal
            return personal
        d.addCallback(_got_personal)

        d.addCallback(lambda dirnode:
                      self.failUnless(IDirectoryNode.providedBy(dirnode), dirnode))
        def get_path(path):
            return self._private_node.get_child_at_path(path)

        d.addCallback(lambda res: get_path(u"personal/sekrit data"))
        d.addCallback(lambda filenode: download_to_data(filenode))
        d.addCallback(lambda data: self.failUnlessEqual(data, self.smalldata))
        d.addCallback(lambda res: get_path(u"s2-rw"))
        d.addCallback(lambda dirnode: self.failUnless(dirnode.is_mutable()))
        d.addCallback(lambda res: get_path(u"s2-ro"))
        def _got_s2ro(dirnode):
            self.failUnless(dirnode.is_mutable(), dirnode)
            self.failUnless(dirnode.is_readonly(), dirnode)
            d1 = defer.succeed(None)
            d1.addCallback(lambda res: dirnode.list())
            d1.addCallback(self.log, "dirnode.list")

            d1.addCallback(lambda res: self.shouldFail2(NotWriteableError, "mkdir(nope)", None, dirnode.create_subdirectory, u"nope"))

            d1.addCallback(self.log, "doing add_file(ro)")
            ut = upload.Data("I will disappear, unrecorded and unobserved. The tragedy of my demise is made more poignant by its silence, but this beauty is not for you to ever know.", convergence="99i-p1x4-xd4-18yc-ywt-87uu-msu-zo -- completely and totally unguessable string (unless you read this)")
            d1.addCallback(lambda res: self.shouldFail2(NotWriteableError, "add_file(nope)", None, dirnode.add_file, u"hope", ut))

            d1.addCallback(self.log, "doing get(ro)")
            d1.addCallback(lambda res: dirnode.get(u"mydata992"))
            d1.addCallback(lambda filenode:
                           self.failUnless(IFileNode.providedBy(filenode)))

            d1.addCallback(self.log, "doing delete(ro)")
            d1.addCallback(lambda res: self.shouldFail2(NotWriteableError, "delete(nope)", None, dirnode.delete, u"mydata992"))

            d1.addCallback(lambda res: self.shouldFail2(NotWriteableError, "set_uri(nope)", None, dirnode.set_uri, u"hopeless", self.uri, self.uri))

            d1.addCallback(lambda res: self.shouldFail2(NoSuchChildError, "get(missing)", "missing", dirnode.get, u"missing"))

            personal = self._personal_node
            d1.addCallback(lambda res: self.shouldFail2(NotWriteableError, "mv from readonly", None, dirnode.move_child_to, u"mydata992", personal, u"nope"))

            d1.addCallback(self.log, "doing move_child_to(ro)2")
            d1.addCallback(lambda res: self.shouldFail2(NotWriteableError, "mv to readonly", None, personal.move_child_to, u"sekrit data", dirnode, u"nope"))

            d1.addCallback(self.log, "finished with _got_s2ro")
            return d1
        d.addCallback(_got_s2ro)
        def _got_home(dummy):
            home = self._private_node
            personal = self._personal_node
            d1 = defer.succeed(None)
            d1.addCallback(self.log, "mv 'P/personal/sekrit data' to P/sekrit")
            d1.addCallback(lambda res:
                           personal.move_child_to(u"sekrit data",home,u"sekrit"))

            d1.addCallback(self.log, "mv P/sekrit 'P/sekrit data'")
            d1.addCallback(lambda res:
                           home.move_child_to(u"sekrit", home, u"sekrit data"))

            d1.addCallback(self.log, "mv 'P/sekret data' P/personal/")
            d1.addCallback(lambda res:
                           home.move_child_to(u"sekrit data", personal))

            d1.addCallback(lambda res: home.build_manifest().when_done())
            d1.addCallback(self.log, "manifest")
            #  five items:
            # P/
            # P/personal/
            # P/personal/sekrit data
            # P/s2-rw  (same as P/s2-ro)
            # P/s2-rw/mydata992 (same as P/s2-rw/mydata992)
            d1.addCallback(lambda res:
                           self.failUnlessEqual(len(res["manifest"]), 5))
            d1.addCallback(lambda res: home.start_deep_stats().when_done())
            def _check_stats(stats):
                expected = {"count-immutable-files": 1,
                            "count-mutable-files": 0,
                            "count-literal-files": 1,
                            "count-files": 2,
                            "count-directories": 3,
                            "size-immutable-files": 112,
                            "size-literal-files": 23,
                            #"size-directories": 616, # varies
                            #"largest-directory": 616,
                            "largest-directory-children": 3,
                            "largest-immutable-file": 112,
                            }
                for k,v in expected.iteritems():
                    self.failUnlessEqual(stats[k], v,
                                         "stats[%s] was %s, not %s" %
                                         (k, stats[k], v))
                self.failUnless(stats["size-directories"] > 1300,
                                stats["size-directories"])
                self.failUnless(stats["largest-directory"] > 800,
                                stats["largest-directory"])
                self.failUnlessEqual(stats["size-files-histogram"],
                                     [ (11, 31, 1), (101, 316, 1) ])
            d1.addCallback(_check_stats)
            return d1
        d.addCallback(_got_home)
        return d

    def shouldFail(self, res, expected_failure, which, substring=None):
        if isinstance(res, Failure):
            res.trap(expected_failure)
            if substring:
                self.failUnless(substring in str(res),
                                "substring '%s' not in '%s'"
                                % (substring, str(res)))
        else:
            self.fail("%s was supposed to raise %s, not get '%s'" %
                      (which, expected_failure, res))

    def shouldFail2(self, expected_failure, which, substring, callable, *args, **kwargs):
        assert substring is None or isinstance(substring, str)
        d = defer.maybeDeferred(callable, *args, **kwargs)
        def done(res):
            if isinstance(res, Failure):
                res.trap(expected_failure)
                if substring:
                    self.failUnless(substring in str(res),
                                    "substring '%s' not in '%s'"
                                    % (substring, str(res)))
            else:
                self.fail("%s was supposed to raise %s, not get '%s'" %
                          (which, expected_failure, res))
        d.addBoth(done)
        return d

    def PUT(self, urlpath, data):
        return do_http("put", self.webish_url + urlpath, data=data)

    def GET(self, urlpath):
        return do_http("get", self.webish_url + urlpath)

    def POST(self, urlpath, use_helper=False, **fields):
        sepbase = "boogabooga"
        sep = "--" + sepbase
        form = []
        form.append(sep)
        form.append('Content-Disposition: form-data; name="_charset"')
        form.append('')
        form.append('UTF-8')
        form.append(sep)
        for name, value in fields.iteritems():
            if isinstance(value, tuple):
                filename, value = value
                form.append('Content-Disposition: form-data; name="%s"; '
                            'filename="%s"' % (name, filename.encode("utf-8")))
            else:
                form.append('Content-Disposition: form-data; name="%s"' % name)
            form.append('')
            form.append(str(value))
            form.append(sep)
        form[-1] += "--"
        body = ""
        headers = {}
        if fields:
            body = "\r\n".join(form) + "\r\n"
            headers["content-type"] = "multipart/form-data; boundary=%s" % sepbase
        return self.POST2(urlpath, body, headers, use_helper)

    def POST2(self, urlpath, body="", headers={}, use_helper=False):
        if use_helper:
            url = self.helper_webish_url + urlpath
        else:
            url = self.webish_url + urlpath
        return do_http("post", url, data=body, headers=headers)

    def _test_web(self, res):
        public = "uri/" + self._root_directory_uri
        d = self.GET("")
        def _got_welcome(page):
            html = page.replace('\n', ' ')
            connected_re = r'Connected to <span>%d</span>\s*of <span>%d</span> known storage servers' % (self.numclients, self.numclients)
            self.failUnless(re.search(connected_re, html),
                            "I didn't see the right '%s' message in:\n%s" % (connected_re, page))
            # nodeids/tubids don't have any regexp-special characters
            nodeid_re = r'<th>Node ID:</th>\s*<td title="TubID: %s">%s</td>' % (
                self.clients[0].get_long_tubid(), self.clients[0].get_long_nodeid())
            self.failUnless(re.search(nodeid_re, html),
                            "I didn't see the right '%s' message in:\n%s" % (nodeid_re, page))
            self.failUnless("Helper: 0 active uploads" in page)
        d.addCallback(_got_welcome)
        d.addCallback(self.log, "done with _got_welcome")

        # get the welcome page from the node that uses the helper too
        d.addCallback(lambda res: do_http("get", self.helper_webish_url))
        def _got_welcome_helper(page):
            soup = BeautifulSoup(page, 'html5lib')
            assert_soup_has_tag_with_attributes(
                self, soup, u"img",
                { u"alt": u"Connected", u"src": u"img/connected-yes.png" }
            )
            self.failUnlessIn("Not running helper", page)
        d.addCallback(_got_welcome_helper)

        d.addCallback(lambda res: self.GET(public))
        d.addCallback(lambda res: self.GET(public + "/subdir1"))
        def _got_subdir1(page):
            # there ought to be an href for our file
            self.failUnlessIn('<td align="right">%d</td>' % len(self.data), page)
            self.failUnless(">mydata567</a>" in page)
        d.addCallback(_got_subdir1)
        d.addCallback(self.log, "done with _got_subdir1")
        d.addCallback(lambda res: self.GET(public + "/subdir1/mydata567"))
        def _got_data(page):
            self.failUnlessEqual(page, self.data)
        d.addCallback(_got_data)

        # download from a URI embedded in a URL
        d.addCallback(self.log, "_get_from_uri")
        def _get_from_uri(res):
            return self.GET("uri/%s?filename=%s" % (self.uri, "mydata567"))
        d.addCallback(_get_from_uri)
        def _got_from_uri(page):
            self.failUnlessEqual(page, self.data)
        d.addCallback(_got_from_uri)

        # download from a URI embedded in a URL, second form
        d.addCallback(self.log, "_get_from_uri2")
        def _get_from_uri2(res):
            return self.GET("uri?uri=%s" % (self.uri,))
        d.addCallback(_get_from_uri2)
        d.addCallback(_got_from_uri)

        # download from a bogus URI, make sure we get a reasonable error
        d.addCallback(self.log, "_get_from_bogus_uri", level=log.UNUSUAL)
        @defer.inlineCallbacks
        def _get_from_bogus_uri(res):
            d1 = self.GET("uri/%s?filename=%s"
                          % (self.mangle_uri(self.uri), "mydata567"))
            e = yield self.assertFailure(d1, Error)
            self.assertEquals(e.status, "410")
        d.addCallback(_get_from_bogus_uri)
        d.addCallback(self.log, "_got_from_bogus_uri", level=log.UNUSUAL)

        # upload a file with PUT
        d.addCallback(self.log, "about to try PUT")
        d.addCallback(lambda res: self.PUT(public + "/subdir3/new.txt",
                                           "new.txt contents"))
        d.addCallback(lambda res: self.GET(public + "/subdir3/new.txt"))
        d.addCallback(self.failUnlessEqual, "new.txt contents")
        # and again with something large enough to use multiple segments,
        # and hopefully trigger pauseProducing too
        def _new_happy_semantics(ign):
            for c in self.clients:
                # these get reset somewhere? Whatever.
                c.encoding_params['happy'] = 1
        d.addCallback(_new_happy_semantics)
        d.addCallback(lambda res: self.PUT(public + "/subdir3/big.txt",
                                           "big" * 500000)) # 1.5MB
        d.addCallback(lambda res: self.GET(public + "/subdir3/big.txt"))
        d.addCallback(lambda res: self.failUnlessEqual(len(res), 1500000))

        # can we replace files in place?
        d.addCallback(lambda res: self.PUT(public + "/subdir3/new.txt",
                                           "NEWER contents"))
        d.addCallback(lambda res: self.GET(public + "/subdir3/new.txt"))
        d.addCallback(self.failUnlessEqual, "NEWER contents")

        # test unlinked POST
        d.addCallback(lambda res: self.POST("uri", t="upload",
                                            file=("new.txt", "data" * 10000)))
        # and again using the helper, which exercises different upload-status
        # display code
        d.addCallback(lambda res: self.POST("uri", use_helper=True, t="upload",
                                            file=("foo.txt", "data2" * 10000)))

        # check that the status page exists
        d.addCallback(lambda res: self.GET("status"))
        def _got_status(res):
            # find an interesting upload and download to look at. LIT files
            # are not interesting.
            h = self.clients[0].get_history()
            for ds in h.list_all_download_statuses():
                if ds.get_size() > 200:
                    self._down_status = ds.get_counter()
            for us in h.list_all_upload_statuses():
                if us.get_size() > 200:
                    self._up_status = us.get_counter()
            rs = list(h.list_all_retrieve_statuses())[0]
            self._retrieve_status = rs.get_counter()
            ps = list(h.list_all_publish_statuses())[0]
            self._publish_status = ps.get_counter()
            us = list(h.list_all_mapupdate_statuses())[0]
            self._update_status = us.get_counter()

            # and that there are some upload- and download- status pages
            return self.GET("status/up-%d" % self._up_status)
        d.addCallback(_got_status)
        def _got_up(res):
            return self.GET("status/down-%d" % self._down_status)
        d.addCallback(_got_up)
        def _got_down(res):
            return self.GET("status/mapupdate-%d" % self._update_status)
        d.addCallback(_got_down)
        def _got_update(res):
            return self.GET("status/publish-%d" % self._publish_status)
        d.addCallback(_got_update)
        def _got_publish(res):
            self.failUnlessIn("Publish Results", res)
            return self.GET("status/retrieve-%d" % self._retrieve_status)
        d.addCallback(_got_publish)
        def _got_retrieve(res):
            self.failUnlessIn("Retrieve Results", res)
        d.addCallback(_got_retrieve)

        # check that the helper status page exists
        d.addCallback(lambda res: self.GET("helper_status"))
        def _got_helper_status(res):
            self.failUnless("Bytes Fetched:" in res)
            # touch a couple of files in the helper's working directory to
            # exercise more code paths
            workdir = os.path.join(self.getdir("client0"), "helper")
            incfile = os.path.join(workdir, "CHK_incoming", "spurious")
            f = open(incfile, "wb")
            f.write("small file")
            f.close()
            then = time.time() - 86400*3
            now = time.time()
            os.utime(incfile, (now, then))
            encfile = os.path.join(workdir, "CHK_encoding", "spurious")
            f = open(encfile, "wb")
            f.write("less small file")
            f.close()
            os.utime(encfile, (now, then))
        d.addCallback(_got_helper_status)
        # and that the json form exists
        d.addCallback(lambda res: self.GET("helper_status?t=json"))
        def _got_helper_status_json(res):
            data = json.loads(res)
            self.failUnlessEqual(data["chk_upload_helper.upload_need_upload"],
                                 1)
            self.failUnlessEqual(data["chk_upload_helper.incoming_count"], 1)
            self.failUnlessEqual(data["chk_upload_helper.incoming_size"], 10)
            self.failUnlessEqual(data["chk_upload_helper.incoming_size_old"],
                                 10)
            self.failUnlessEqual(data["chk_upload_helper.encoding_count"], 1)
            self.failUnlessEqual(data["chk_upload_helper.encoding_size"], 15)
            self.failUnlessEqual(data["chk_upload_helper.encoding_size_old"],
                                 15)
        d.addCallback(_got_helper_status_json)

        # and check that client[3] (which uses a helper but does not run one
        # itself) doesn't explode when you ask for its status
        d.addCallback(lambda res: do_http("get",
                                          self.helper_webish_url + "status/"))
        def _got_non_helper_status(res):
            self.failUnlessIn("Recent and Active Operations", res)
        d.addCallback(_got_non_helper_status)

        # or for helper status with t=json
        d.addCallback(lambda res:
                      do_http("get",
                              self.helper_webish_url + "helper_status?t=json"))
        def _got_non_helper_status_json(res):
            data = json.loads(res)
            self.failUnlessEqual(data, {})
        d.addCallback(_got_non_helper_status_json)

        # see if the statistics page exists
        d.addCallback(lambda res: self.GET("statistics"))
        def _got_stats(res):
            self.failUnlessIn("Operational Statistics", res)
            self.failUnlessIn("  'downloader.files_downloaded': 5,", res)
        d.addCallback(_got_stats)
        d.addCallback(lambda res: self.GET("statistics?t=json"))
        def _got_stats_json(res):
            data = json.loads(res)
            self.failUnlessEqual(data["counters"]["uploader.files_uploaded"], 5)
            self.failUnlessEqual(data["stats"]["chk_upload_helper.upload_need_upload"], 1)
        d.addCallback(_got_stats_json)

        # TODO: mangle the second segment of a file, to test errors that
        # occur after we've already sent some good data, which uses a
        # different error path.

        # TODO: download a URI with a form
        # TODO: create a directory by using a form
        # TODO: upload by using a form on the directory page
        #    url = base + "somedir/subdir1/freeform_post!!upload"
        # TODO: delete a file by using a button on the directory page

        return d

    @defer.inlineCallbacks
    def _test_runner(self, res):
        # exercise some of the diagnostic tools in runner.py

        # find a share
        for (dirpath, dirnames, filenames) in os.walk(unicode(self.basedir)):
            if "storage" not in dirpath:
                continue
            if not filenames:
                continue
            pieces = dirpath.split(os.sep)
            if (len(pieces) >= 4
                and pieces[-4] == "storage"
                and pieces[-3] == "shares"):
                # we're sitting in .../storage/shares/$START/$SINDEX , and there
                # are sharefiles here
                filename = os.path.join(dirpath, filenames[0])
                # peek at the magic to see if it is a chk share
                magic = open(filename, "rb").read(4)
                if magic == '\x00\x00\x00\x01':
                    break
        else:
            self.fail("unable to find any uri_extension files in %r"
                      % self.basedir)
        log.msg("test_system.SystemTest._test_runner using %r" % filename)

        rc,output,err = yield run_cli("debug", "dump-share", "--offsets",
                                      unicode_to_argv(filename))
        self.failUnlessEqual(rc, 0)

        # we only upload a single file, so we can assert some things about
        # its size and shares.
        self.failUnlessIn("share filename: %s" % quote_output(abspath_expanduser_unicode(filename)), output)
        self.failUnlessIn("size: %d\n" % len(self.data), output)
        self.failUnlessIn("num_segments: 1\n", output)
        # segment_size is always a multiple of needed_shares
        self.failUnlessIn("segment_size: %d\n" % mathutil.next_multiple(len(self.data), 3), output)
        self.failUnlessIn("total_shares: 10\n", output)
        # keys which are supposed to be present
        for key in ("size", "num_segments", "segment_size",
                    "needed_shares", "total_shares",
                    "codec_name", "codec_params", "tail_codec_params",
                    #"plaintext_hash", "plaintext_root_hash",
                    "crypttext_hash", "crypttext_root_hash",
                    "share_root_hash", "UEB_hash"):
            self.failUnlessIn("%s: " % key, output)
        self.failUnlessIn("  verify-cap: URI:CHK-Verifier:", output)

        # now use its storage index to find the other shares using the
        # 'find-shares' tool
        sharedir, shnum = os.path.split(filename)
        storagedir, storage_index_s = os.path.split(sharedir)
        storage_index_s = str(storage_index_s)
        nodedirs = [self.getdir("client%d" % i) for i in range(self.numclients)]
        rc,out,err = yield run_cli("debug", "find-shares", storage_index_s,
                                   *nodedirs)
        self.failUnlessEqual(rc, 0)
        sharefiles = [sfn.strip() for sfn in out.splitlines()]
        self.failUnlessEqual(len(sharefiles), 10)

        # also exercise the 'catalog-shares' tool
        nodedirs = [self.getdir("client%d" % i) for i in range(self.numclients)]
        rc,out,err = yield run_cli("debug", "catalog-shares", *nodedirs)
        self.failUnlessEqual(rc, 0)
        descriptions = [sfn.strip() for sfn in out.splitlines()]
        self.failUnlessEqual(len(descriptions), 30)
        matching = [line
                    for line in descriptions
                    if line.startswith("CHK %s " % storage_index_s)]
        self.failUnlessEqual(len(matching), 10)

    def _test_control(self, res):
        # exercise the remote-control-the-client foolscap interfaces in
        # allmydata.control (mostly used for performance tests)
        c0 = self.clients[0]
        control_furl_file = c0.config.get_private_path("control.furl")
        control_furl = open(control_furl_file, "r").read().strip()
        # it doesn't really matter which Tub we use to connect to the client,
        # so let's just use our IntroducerNode's
        d = self.introducer.tub.getReference(control_furl)
        d.addCallback(self._test_control2, control_furl_file)
        return d
    def _test_control2(self, rref, filename):
        d = defer.succeed(None)
        d.addCallback(lambda res: rref.callRemote("speed_test", 1, 200, False))
        if sys.platform in ("linux2", "linux3"):
            d.addCallback(lambda res: rref.callRemote("get_memory_usage"))
        d.addCallback(lambda res: rref.callRemote("measure_peer_response_time"))
        return d

    def _test_cli(self, res):
        # run various CLI commands (in a thread, since they use blocking
        # network calls)

        private_uri = self._private_node.get_uri()
        client0_basedir = self.getdir("client0")

        nodeargs = [
            "--node-directory", client0_basedir,
            ]

        d = defer.succeed(None)

        # for compatibility with earlier versions, private/root_dir.cap is
        # supposed to be treated as an alias named "tahoe:". Start by making
        # sure that works, before we add other aliases.

        root_file = os.path.join(client0_basedir, "private", "root_dir.cap")
        f = open(root_file, "w")
        f.write(private_uri)
        f.close()

        @defer.inlineCallbacks
        def run(ignored, verb, *args, **kwargs):
            rc,out,err = yield run_cli(verb, *args, nodeargs=nodeargs, **kwargs)
            defer.returnValue((out,err))

        def _check_ls(out_and_err, expected_children, unexpected_children=[]):
            (out, err) = out_and_err
            self.failUnlessEqual(err, "")
            for s in expected_children:
                self.failUnless(s in out, (s,out))
            for s in unexpected_children:
                self.failIf(s in out, (s,out))

        def _check_ls_root(out_and_err):
            (out, err) = out_and_err
            self.failUnless("personal" in out)
            self.failUnless("s2-ro" in out)
            self.failUnless("s2-rw" in out)
            self.failUnlessEqual(err, "")

        # this should reference private_uri
        d.addCallback(run, "ls")
        d.addCallback(_check_ls, ["personal", "s2-ro", "s2-rw"])

        d.addCallback(run, "list-aliases")
        def _check_aliases_1(out_and_err):
            (out, err) = out_and_err
            self.failUnlessEqual(err, "")
            self.failUnlessEqual(out.strip(" \n"), "tahoe: %s" % private_uri)
        d.addCallback(_check_aliases_1)

        # now that that's out of the way, remove root_dir.cap and work with
        # new files
        d.addCallback(lambda res: os.unlink(root_file))
        d.addCallback(run, "list-aliases")
        def _check_aliases_2(out_and_err):
            (out, err) = out_and_err
            self.failUnlessEqual(err, "")
            self.failUnlessEqual(out, "")
        d.addCallback(_check_aliases_2)

        d.addCallback(run, "mkdir")
        def _got_dir(out_and_err ):
            (out, err) = out_and_err
            self.failUnless(uri.from_string_dirnode(out.strip()))
            return out.strip()
        d.addCallback(_got_dir)
        d.addCallback(lambda newcap: run(None, "add-alias", "tahoe", newcap))

        d.addCallback(run, "list-aliases")
        def _check_aliases_3(out_and_err):
            (out, err) = out_and_err
            self.failUnlessEqual(err, "")
            self.failUnless("tahoe: " in out)
        d.addCallback(_check_aliases_3)

        def _check_empty_dir(out_and_err):
            (out, err) = out_and_err
            self.failUnlessEqual(out, "")
            self.failUnlessEqual(err, "")
        d.addCallback(run, "ls")
        d.addCallback(_check_empty_dir)

        def _check_missing_dir(out_and_err):
            # TODO: check that rc==2
            (out, err) = out_and_err
            self.failUnlessEqual(out, "")
            self.failUnlessEqual(err, "No such file or directory\n")
        d.addCallback(run, "ls", "bogus")
        d.addCallback(_check_missing_dir)

        files = []
        datas = []
        for i in range(10):
            fn = os.path.join(self.basedir, "file%d" % i)
            files.append(fn)
            data = "data to be uploaded: file%d\n" % i
            datas.append(data)
            open(fn,"wb").write(data)

        def _check_stdout_against(out_and_err, filenum=None, data=None):
            (out, err) = out_and_err
            self.failUnlessEqual(err, "")
            if filenum is not None:
                self.failUnlessEqual(out, datas[filenum])
            if data is not None:
                self.failUnlessEqual(out, data)

        # test all both forms of put: from a file, and from stdin
        #  tahoe put bar FOO
        d.addCallback(run, "put", files[0], "tahoe-file0")
        def _put_out(out_and_err):
            (out, err) = out_and_err
            self.failUnless("URI:LIT:" in out, out)
            self.failUnless("201 Created" in err, err)
            uri0 = out.strip()
            return run(None, "get", uri0)
        d.addCallback(_put_out)
        d.addCallback(lambda out_err: self.failUnlessEqual(out_err[0], datas[0]))

        d.addCallback(run, "put", files[1], "subdir/tahoe-file1")
        #  tahoe put bar tahoe:FOO
        d.addCallback(run, "put", files[2], "tahoe:file2")
        d.addCallback(run, "put", "--format=SDMF", files[3], "tahoe:file3")
        def _check_put_mutable(out_and_err):
            (out, err) = out_and_err
            self._mutable_file3_uri = out.strip()
        d.addCallback(_check_put_mutable)
        d.addCallback(run, "get", "tahoe:file3")
        d.addCallback(_check_stdout_against, 3)

        #  tahoe put FOO
        STDIN_DATA = "This is the file to upload from stdin."
        d.addCallback(run, "put", "-", "tahoe-file-stdin", stdin=STDIN_DATA)
        #  tahoe put tahoe:FOO
        d.addCallback(run, "put", "-", "tahoe:from-stdin",
                      stdin="Other file from stdin.")

        d.addCallback(run, "ls")
        d.addCallback(_check_ls, ["tahoe-file0", "file2", "file3", "subdir",
                                  "tahoe-file-stdin", "from-stdin"])
        d.addCallback(run, "ls", "subdir")
        d.addCallback(_check_ls, ["tahoe-file1"])

        # tahoe mkdir FOO
        d.addCallback(run, "mkdir", "subdir2")
        d.addCallback(run, "ls")
        # TODO: extract the URI, set an alias with it
        d.addCallback(_check_ls, ["subdir2"])

        # tahoe get: (to stdin and to a file)
        d.addCallback(run, "get", "tahoe-file0")
        d.addCallback(_check_stdout_against, 0)
        d.addCallback(run, "get", "tahoe:subdir/tahoe-file1")
        d.addCallback(_check_stdout_against, 1)
        outfile0 = os.path.join(self.basedir, "outfile0")
        d.addCallback(run, "get", "file2", outfile0)
        def _check_outfile0(out_and_err):
            (out, err) = out_and_err
            data = open(outfile0,"rb").read()
            self.failUnlessEqual(data, "data to be uploaded: file2\n")
        d.addCallback(_check_outfile0)
        outfile1 = os.path.join(self.basedir, "outfile0")
        d.addCallback(run, "get", "tahoe:subdir/tahoe-file1", outfile1)
        def _check_outfile1(out_and_err):
            (out, err) = out_and_err
            data = open(outfile1,"rb").read()
            self.failUnlessEqual(data, "data to be uploaded: file1\n")
        d.addCallback(_check_outfile1)

        d.addCallback(run, "unlink", "tahoe-file0")
        d.addCallback(run, "unlink", "tahoe:file2")
        d.addCallback(run, "ls")
        d.addCallback(_check_ls, [], ["tahoe-file0", "file2"])

        d.addCallback(run, "ls", "-l")
        def _check_ls_l(out_and_err):
            (out, err) = out_and_err
            lines = out.split("\n")
            for l in lines:
                if "tahoe-file-stdin" in l:
                    self.failUnless(l.startswith("-r-- "), l)
                    self.failUnless(" %d " % len(STDIN_DATA) in l)
                if "file3" in l:
                    self.failUnless(l.startswith("-rw- "), l) # mutable
        d.addCallback(_check_ls_l)

        d.addCallback(run, "ls", "--uri")
        def _check_ls_uri(out_and_err):
            (out, err) = out_and_err
            lines = out.split("\n")
            for l in lines:
                if "file3" in l:
                    self.failUnless(self._mutable_file3_uri in l)
        d.addCallback(_check_ls_uri)

        d.addCallback(run, "ls", "--readonly-uri")
        def _check_ls_rouri(out_and_err):
            (out, err) = out_and_err
            lines = out.split("\n")
            for l in lines:
                if "file3" in l:
                    rw_uri = self._mutable_file3_uri
                    u = uri.from_string_mutable_filenode(rw_uri)
                    ro_uri = u.get_readonly().to_string()
                    self.failUnless(ro_uri in l)
        d.addCallback(_check_ls_rouri)


        d.addCallback(run, "mv", "tahoe-file-stdin", "tahoe-moved")
        d.addCallback(run, "ls")
        d.addCallback(_check_ls, ["tahoe-moved"], ["tahoe-file-stdin"])

        d.addCallback(run, "ln", "tahoe-moved", "newlink")
        d.addCallback(run, "ls")
        d.addCallback(_check_ls, ["tahoe-moved", "newlink"])

        d.addCallback(run, "cp", "tahoe:file3", "tahoe:file3-copy")
        d.addCallback(run, "ls")
        d.addCallback(_check_ls, ["file3", "file3-copy"])
        d.addCallback(run, "get", "tahoe:file3-copy")
        d.addCallback(_check_stdout_against, 3)

        # copy from disk into tahoe
        d.addCallback(run, "cp", files[4], "tahoe:file4")
        d.addCallback(run, "ls")
        d.addCallback(_check_ls, ["file3", "file3-copy", "file4"])
        d.addCallback(run, "get", "tahoe:file4")
        d.addCallback(_check_stdout_against, 4)

        # copy from tahoe into disk
        target_filename = os.path.join(self.basedir, "file-out")
        d.addCallback(run, "cp", "tahoe:file4", target_filename)
        def _check_cp_out(out_and_err):
            (out, err) = out_and_err
            self.failUnless(os.path.exists(target_filename))
            got = open(target_filename,"rb").read()
            self.failUnlessEqual(got, datas[4])
        d.addCallback(_check_cp_out)

        # copy from disk to disk (silly case)
        target2_filename = os.path.join(self.basedir, "file-out-copy")
        d.addCallback(run, "cp", target_filename, target2_filename)
        def _check_cp_out2(out_and_err):
            (out, err) = out_and_err
            self.failUnless(os.path.exists(target2_filename))
            got = open(target2_filename,"rb").read()
            self.failUnlessEqual(got, datas[4])
        d.addCallback(_check_cp_out2)

        # copy from tahoe into disk, overwriting an existing file
        d.addCallback(run, "cp", "tahoe:file3", target_filename)
        def _check_cp_out3(out_and_err):
            (out, err) = out_and_err
            self.failUnless(os.path.exists(target_filename))
            got = open(target_filename,"rb").read()
            self.failUnlessEqual(got, datas[3])
        d.addCallback(_check_cp_out3)

        # copy from disk into tahoe, overwriting an existing immutable file
        d.addCallback(run, "cp", files[5], "tahoe:file4")
        d.addCallback(run, "ls")
        d.addCallback(_check_ls, ["file3", "file3-copy", "file4"])
        d.addCallback(run, "get", "tahoe:file4")
        d.addCallback(_check_stdout_against, 5)

        # copy from disk into tahoe, overwriting an existing mutable file
        d.addCallback(run, "cp", files[5], "tahoe:file3")
        d.addCallback(run, "ls")
        d.addCallback(_check_ls, ["file3", "file3-copy", "file4"])
        d.addCallback(run, "get", "tahoe:file3")
        d.addCallback(_check_stdout_against, 5)

        # recursive copy: setup
        dn = os.path.join(self.basedir, "dir1")
        os.makedirs(dn)
        open(os.path.join(dn, "rfile1"), "wb").write("rfile1")
        open(os.path.join(dn, "rfile2"), "wb").write("rfile2")
        open(os.path.join(dn, "rfile3"), "wb").write("rfile3")
        sdn2 = os.path.join(dn, "subdir2")
        os.makedirs(sdn2)
        open(os.path.join(sdn2, "rfile4"), "wb").write("rfile4")
        open(os.path.join(sdn2, "rfile5"), "wb").write("rfile5")

        # from disk into tahoe
        d.addCallback(run, "cp", "-r", dn, "tahoe:")
        d.addCallback(run, "ls")
        d.addCallback(_check_ls, ["dir1"])
        d.addCallback(run, "ls", "dir1")
        d.addCallback(_check_ls, ["rfile1", "rfile2", "rfile3", "subdir2"],
                      ["rfile4", "rfile5"])
        d.addCallback(run, "ls", "tahoe:dir1/subdir2")
        d.addCallback(_check_ls, ["rfile4", "rfile5"],
                      ["rfile1", "rfile2", "rfile3"])
        d.addCallback(run, "get", "dir1/subdir2/rfile4")
        d.addCallback(_check_stdout_against, data="rfile4")

        # and back out again
        dn_copy = os.path.join(self.basedir, "dir1-copy")
        d.addCallback(run, "cp", "--verbose", "-r", "tahoe:dir1", dn_copy)
        def _check_cp_r_out(out_and_err):
            (out, err) = out_and_err
            def _cmp(name):
                old = open(os.path.join(dn, name), "rb").read()
                newfn = os.path.join(dn_copy, "dir1", name)
                self.failUnless(os.path.exists(newfn))
                new = open(newfn, "rb").read()
                self.failUnlessEqual(old, new)
            _cmp("rfile1")
            _cmp("rfile2")
            _cmp("rfile3")
            _cmp(os.path.join("subdir2", "rfile4"))
            _cmp(os.path.join("subdir2", "rfile5"))
        d.addCallback(_check_cp_r_out)

        # and copy it a second time, which ought to overwrite the same files
        d.addCallback(run, "cp", "-r", "tahoe:dir1", dn_copy)

        # and again, only writing filecaps
        dn_copy2 = os.path.join(self.basedir, "dir1-copy-capsonly")
        d.addCallback(run, "cp", "-r", "--caps-only", "tahoe:dir1", dn_copy2)
        def _check_capsonly(out_and_err):
            # these should all be LITs
            (out, err) = out_and_err
            x = open(os.path.join(dn_copy2, "dir1", "subdir2", "rfile4")).read()
            y = uri.from_string_filenode(x)
            self.failUnlessEqual(y.data, "rfile4")
        d.addCallback(_check_capsonly)

        # and tahoe-to-tahoe
        d.addCallback(run, "cp", "-r", "tahoe:dir1", "tahoe:dir1-copy")
        d.addCallback(run, "ls")
        d.addCallback(_check_ls, ["dir1", "dir1-copy"])
        d.addCallback(run, "ls", "dir1-copy/dir1")
        d.addCallback(_check_ls, ["rfile1", "rfile2", "rfile3", "subdir2"],
                      ["rfile4", "rfile5"])
        d.addCallback(run, "ls", "tahoe:dir1-copy/dir1/subdir2")
        d.addCallback(_check_ls, ["rfile4", "rfile5"],
                      ["rfile1", "rfile2", "rfile3"])
        d.addCallback(run, "get", "dir1-copy/dir1/subdir2/rfile4")
        d.addCallback(_check_stdout_against, data="rfile4")

        # and copy it a second time, which ought to overwrite the same files
        d.addCallback(run, "cp", "-r", "tahoe:dir1", "tahoe:dir1-copy")

        # tahoe_ls doesn't currently handle the error correctly: it tries to
        # JSON-parse a traceback.
##         def _ls_missing(res):
##             argv = nodeargs + ["ls", "bogus"]
##             return self._run_cli(argv)
##         d.addCallback(_ls_missing)
##         def _check_ls_missing((out,err)):
##             print("OUT", out)
##             print("ERR", err)
##             self.failUnlessEqual(err, "")
##         d.addCallback(_check_ls_missing)

        return d

    def test_filesystem_with_cli_in_subprocess(self):
        # We do this in a separate test so that test_filesystem doesn't skip if we can't run bin/tahoe.

        self.basedir = "system/SystemTest/test_filesystem_with_cli_in_subprocess"
        d = self.set_up_nodes()
        def _new_happy_semantics(ign):
            for c in self.clients:
                c.encoding_params['happy'] = 1
        d.addCallback(_new_happy_semantics)

        def _run_in_subprocess(ignored, verb, *args, **kwargs):
            stdin = kwargs.get("stdin")
            env = kwargs.get("env", os.environ)
            # Python warnings from the child process don't matter.
            env["PYTHONWARNINGS"] = "ignore"
            newargs = ["--node-directory", self.getdir("client0"), verb] + list(args)
            return self.run_bintahoe(newargs, stdin=stdin, env=env)

        def _check_succeeded(res, check_stderr=True):
            out, err, rc_or_sig = res
            self.failUnlessEqual(rc_or_sig, 0, str(res))
            if check_stderr:
                self.failUnlessEqual(err, "")

        d.addCallback(_run_in_subprocess, "create-alias", "newalias")
        d.addCallback(_check_succeeded)

        STDIN_DATA = "This is the file to upload from stdin."
        d.addCallback(_run_in_subprocess, "put", "-", "newalias:tahoe-file", stdin=STDIN_DATA)
        d.addCallback(_check_succeeded, check_stderr=False)

        def _mv_with_http_proxy(ign):
            env = os.environ
            env['http_proxy'] = env['HTTP_PROXY'] = "http://127.0.0.0:12345"  # invalid address
            return _run_in_subprocess(None, "mv", "newalias:tahoe-file", "newalias:tahoe-moved", env=env)
        d.addCallback(_mv_with_http_proxy)
        d.addCallback(_check_succeeded)

        d.addCallback(_run_in_subprocess, "ls", "newalias:")
        def _check_ls(res):
            out, err, rc_or_sig = res
            self.failUnlessEqual(rc_or_sig, 0, str(res))
            self.failUnlessEqual(err, "", str(res))
            self.failUnlessIn("tahoe-moved", out)
            self.failIfIn("tahoe-file", out)
        d.addCallback(_check_ls)
        return d

    def _test_checker(self, res):
        ut = upload.Data("too big to be literal" * 200, convergence=None)
        d = self._personal_node.add_file(u"big file", ut)

        d.addCallback(lambda res: self._personal_node.check(Monitor()))
        def _check_dirnode_results(r):
            self.failUnless(r.is_healthy())
        d.addCallback(_check_dirnode_results)
        d.addCallback(lambda res: self._personal_node.check(Monitor(), verify=True))
        d.addCallback(_check_dirnode_results)

        d.addCallback(lambda res: self._personal_node.get(u"big file"))
        def _got_chk_filenode(n):
            self.failUnless(isinstance(n, ImmutableFileNode))
            d = n.check(Monitor())
            def _check_filenode_results(r):
                self.failUnless(r.is_healthy())
            d.addCallback(_check_filenode_results)
            d.addCallback(lambda res: n.check(Monitor(), verify=True))
            d.addCallback(_check_filenode_results)
            return d
        d.addCallback(_got_chk_filenode)

        d.addCallback(lambda res: self._personal_node.get(u"sekrit data"))
        def _got_lit_filenode(n):
            self.failUnless(isinstance(n, LiteralFileNode))
            d = n.check(Monitor())
            def _check_lit_filenode_results(r):
                self.failUnlessEqual(r, None)
            d.addCallback(_check_lit_filenode_results)
            d.addCallback(lambda res: n.check(Monitor(), verify=True))
            d.addCallback(_check_lit_filenode_results)
            return d
        d.addCallback(_got_lit_filenode)
        return d


class Connections(SystemTestMixin, unittest.TestCase):

    def test_rref(self):
        self.basedir = "system/Connections/rref"
        d = self.set_up_nodes(2)
        def _start(ign):
            self.c0 = self.clients[0]
            nonclients = [s for s in self.c0.storage_broker.get_connected_servers()
                          if s.get_serverid() != self.c0.get_long_nodeid()]
            self.failUnlessEqual(len(nonclients), 1)

            self.s1 = nonclients[0]  # s1 is the server, not c0
            self.s1_storage_server = self.s1.get_storage_server()
            self.assertIsNot(self.s1_storage_server, None)
            self.assertTrue(self.s1.is_connected())
        d.addCallback(_start)

        # now shut down the server
        d.addCallback(lambda ign: self.clients[1].disownServiceParent())
        # and wait for the client to notice
        def _poll():
            return len(self.c0.storage_broker.get_connected_servers()) < 2
        d.addCallback(lambda ign: self.poll(_poll))

        def _down(ign):
            self.assertFalse(self.s1.is_connected())
            storage_server = self.s1.get_storage_server()
            self.assertIsNot(storage_server, None)
            self.assertEqual(storage_server, self.s1_storage_server)
        d.addCallback(_down)
        return d
