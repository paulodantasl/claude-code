import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.parser import parse_assignment_email  # noqa: E402

SAMPLES = os.path.join(os.path.dirname(__file__), "sample_emails")


def load(name):
    with open(os.path.join(SAMPLES, name), encoding="utf-8") as f:
        return f.read()


class TestAssignmentParser(unittest.TestCase):
    def setUp(self):
        self.lead = parse_assignment_email(
            load("sample_assignment.txt"),
            subject="XactAnalysis New Assignment - Claim ABC-2026-0421337",
            message_id="<test-1@xactanalysis.test>",
        )

    def test_core_fields(self):
        self.assertEqual(self.lead.claim_number, "ABC-2026-0421337")
        self.assertEqual(self.lead.insured_name, "Jane Q. Sample")
        self.assertEqual(self.lead.type_of_loss, "Water")
        self.assertEqual(self.lead.date_of_loss, "07/28/2026")
        self.assertEqual(self.lead.carrier, "Example Mutual Insurance")
        self.assertEqual(self.lead.policy_number, "HO-99182734")

    def test_two_line_address_joined(self):
        self.assertEqual(
            self.lead.loss_address,
            "4821 Example Ave N, St. Petersburg, FL 33710",
        )

    def test_adjuster_fields(self):
        self.assertEqual(self.lead.adjuster_name, "Alex Casefile")
        self.assertEqual(self.lead.adjuster_phone, "(800) 555-0100")
        self.assertEqual(self.lead.adjuster_email, "acasefile@examplemutual.test")

    def test_is_assignment(self):
        self.assertTrue(self.lead.is_assignment)

    def test_job_name(self):
        self.assertEqual(
            self.lead.job_name(),
            "Claim ABC-2026-0421337 — Jane Q. Sample — Water",
        )

    def test_description_contains_original(self):
        self.assertIn("Original notification", self.lead.description())
        self.assertIn("Loss address: 4821 Example Ave N, St. Petersburg, FL 33710",
                      self.lead.description())

    def test_claim_number_from_subject_fallback(self):
        lead = parse_assignment_email(
            "A new work assignment is waiting for you.",
            subject="New Assignment Claim #XYZ-777",
        )
        self.assertEqual(lead.claim_number, "XYZ-777")
        self.assertTrue(lead.is_assignment)

    def test_non_assignment_email_rejected(self):
        lead = parse_assignment_email(
            "Your weekly newsletter", subject="Industry news roundup"
        )
        self.assertFalse(lead.is_assignment)


if __name__ == "__main__":
    unittest.main()
