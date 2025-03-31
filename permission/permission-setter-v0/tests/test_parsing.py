import unittest

from permission_setter.schemas.models import AclRecord
from permission_setter.schemas.parsers import decode_acl, encode_acl

EXAMPLE_ACL_MAPPING = {
    'user:foo:rwx,group:bar:r-x,other::---': (
        AclRecord('user', 'foo', 'rwx'),
        AclRecord('group', 'bar', 'r-x'),
        AclRecord('other', '', '---'),
    ),
}


class TestAclPrserFunction(unittest.TestCase):
    def test_deserialize(self):
        for acl_str, acl in EXAMPLE_ACL_MAPPING.items():
            with self.subTest(acl_str=acl_str):
                decoded_acl = decode_acl(acl_str)
                self.assertSequenceEqual(decoded_acl, acl)

    def test_serialize(self):
        for acl_str, acl in EXAMPLE_ACL_MAPPING.items():
            with self.subTest(acl_str=acl_str):
                encoded_acl = encode_acl(acl)
                self.assertEqual(encoded_acl, acl_str)

    def test_decode_encode_returns_initial(self):
        for acl_str in EXAMPLE_ACL_MAPPING:
            with self.subTest(acl_str=acl_str):
                decoded_acl = decode_acl(acl_str)
                encoded_acl = encode_acl(decoded_acl)

                self.assertEqual(acl_str, encoded_acl)

    def test_encode_decode_returns_initial(self):
        for acl in EXAMPLE_ACL_MAPPING.values():
            with self.subTest(acl=acl):
                encoded_acl = encode_acl(acl)
                decoded_acl = decode_acl(encoded_acl)

                self.assertSequenceEqual(decoded_acl, acl)
