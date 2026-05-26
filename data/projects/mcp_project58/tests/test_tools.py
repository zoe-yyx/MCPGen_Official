"""Unit tests for tool functions — direct Python calls, no MCP."""

import csv
import json
import os
import shutil
import tempfile
import unittest

from mcp_server.tools.leads_tools import (
    get_leads,
    filter_unresearched_leads,
    update_lead_research,
    update_lead_status,
    get_email_template,
    get_services,
    save_email_draft,
    encode_company_url,
    save_send_link,
)
from mcp_server.tools.research_tools import search_internet


class TestLeadsTools(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Create test leads CSV
        self.leads_path = os.path.join(self.test_dir, "leads.csv")
        with open(self.leads_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Nama", "Jabatan", "Email", "Perusahaan",
                "Hasil Riset", "Status", "Send Email Perkenalan", "Kirim email",
            ])
            writer.writeheader()
            writer.writerow({
                "Nama": "Alice", "Jabatan": "CTO", "Email": "EMAIL_PLACEHOLDER",
                "Perusahaan": "Acme Corp", "Hasil Riset": "", "Status": "",
                "Send Email Perkenalan": "", "Kirim email": "",
            })
            writer.writerow({
                "Nama": "Bob", "Jabatan": "CEO", "Email": "EMAIL_PLACEHOLDER",
                "Perusahaan": "Beta Inc", "Hasil Riset": "Already researched",
                "Status": "Leads", "Send Email Perkenalan": "", "Kirim email": "",
            })

        # Create test templates CSV
        self.templates_path = os.path.join(self.test_dir, "templates.csv")
        with open(self.templates_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Tahap", "Tema", "Contoh message"])
            writer.writeheader()
            writer.writerow({
                "Tahap": "Leads", "Tema": "Introduction",
                "Contoh message": "Hello, I'd like to introduce our services.",
            })

        # Create test services CSV
        self.services_path = os.path.join(self.test_dir, "services.csv")
        with open(self.services_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Product", "Description"])
            writer.writeheader()
            writer.writerow({"Product": "AI Bot", "Description": "Smart chatbot"})

    def test_get_leads(self):
        leads = get_leads(self.leads_path)
        self.assertEqual(len(leads), 2)
        self.assertEqual(leads[0]["Perusahaan"], "Acme Corp")

    def test_filter_unresearched_leads(self):
        leads = get_leads(self.leads_path)
        filtered = filter_unresearched_leads(json.dumps(leads))
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["Perusahaan"], "Acme Corp")

    def test_update_lead_research(self):
        result = update_lead_research(self.leads_path, "Acme Corp", "Research text here")
        self.assertEqual(result["status"], "updated")
        leads = get_leads(self.leads_path)
        self.assertEqual(leads[0]["Hasil Riset"], "Research text here")

    def test_update_lead_research_not_found(self):
        result = update_lead_research(self.leads_path, "Nonexistent", "text")
        self.assertEqual(result["status"], "not_found")

    def test_update_lead_status(self):
        result = update_lead_status(self.leads_path, "Acme Corp", "Leads")
        self.assertEqual(result["status"], "updated")
        leads = get_leads(self.leads_path)
        self.assertEqual(leads[0]["Status"], "Leads")

    def test_get_email_template(self):
        template = get_email_template(self.templates_path, "Leads")
        self.assertEqual(template["Tema"], "Introduction")

    def test_get_email_template_not_found(self):
        template = get_email_template(self.templates_path, "Nonexistent")
        self.assertEqual(template["Tahap"], "Nonexistent")

    def test_get_services(self):
        services = get_services(self.services_path)
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0]["Product"], "AI Bot")

    def test_save_email_draft(self):
        draft = json.dumps({"emailSubject": "Test", "emailBody": "Hello"})
        result = save_email_draft(self.leads_path, "Acme Corp", draft)
        self.assertEqual(result["status"], "updated")

    def test_encode_company_url(self):
        result = encode_company_url("Bank BCA")
        self.assertEqual(result["encoded"], "Bank%20BCA")

    def test_encode_company_url_special(self):
        result = encode_company_url("PT Telkom & Sons")
        self.assertIn("%26", result["encoded"])

    def test_save_send_link(self):
        result = save_send_link(self.leads_path, "Acme Corp", "ENDPOINT_PLACEHOLDER")
        self.assertEqual(result["status"], "updated")
        leads = get_leads(self.leads_path)
        self.assertEqual(leads[0]["Kirim email"], "ENDPOINT_PLACEHOLDER")


class TestResearchTools(unittest.TestCase):

    def test_search_internet_known_company(self):
        result = search_internet("Bank BCA digital transformation")
        self.assertIn("BCA", result)
        self.assertGreater(len(result), 50)

    def test_search_internet_unknown(self):
        result = search_internet("random unknown query xyz")
        self.assertIn("AI", result)

    def test_search_internet_telkom(self):
        result = search_internet("Telkom Indonesia overview")
        self.assertIn("Telkom", result)


if __name__ == "__main__":
    unittest.main()
