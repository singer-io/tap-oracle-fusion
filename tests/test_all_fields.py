"""All-fields test for tap-oracle-fusion.

Verifies that when all streams and fields are selected, every field present
in the discovered schema is emitted to the target.  Because tap-oracle-fusion
uses dynamic schemas (derived from BICC datastore attribute metadata at
runtime), the expected fields are taken directly from the discovered catalog
rather than from static fixtures.

Known missing fields can be declared in ``KNOWN_MISSING_FIELDS`` if an
Oracle Fusion environment does not return values for certain schema fields.
"""

from base import OracleFusionBaseTest
from tap_tester.base_suite_tests.all_fields_test import AllFieldsTest


# Fields that are present in the schema but consistently absent from API
# responses for a given stream.  Keyed by stream name (tap_stream_id).
# Example:
#   KNOWN_MISSING_FIELDS = {
#       "fscmtopmodelam_finextractam_arbiccextractam_salescredittypeextractpvo": {
#           "SomeFieldThatNeverHasData",
#       },
#   }
KNOWN_MISSING_FIELDS = {}


class OracleFusionAllFields(AllFieldsTest, OracleFusionBaseTest):
    """Ensure running the tap with all fields selected results in the
    replication of all schema fields for every tested stream."""

    # Populate with stream-level missing fields if Oracle Fusion returns
    # records that consistently omit certain schema fields.
    MISSING_FIELDS = KNOWN_MISSING_FIELDS

    @staticmethod
    def name():
        return "tap_tester_oracle_fusion_all_fields_test"

    def streams_to_test(self):
        return self.expected_stream_names()
