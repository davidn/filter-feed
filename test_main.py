
import unittest
import xml.etree.ElementTree as ET

from main import detectRss, detectAtom, modifyRss, modifyAtom
from filter_feed import FilterFeed

class DetectTest(unittest.TestCase):
    def test_RSSFromXML(self):
      xml = ET.fromstring(
              "<rss></rss>"
              )
      ct = "application/xml"
      self.assertTrue(detectRss(ct, xml))
      self.assertFalse(detectAtom(ct, xml))

    def test_AtomFromXML(self):
      xml = ET.fromstring(
              "<feed></feed>"
              )
      ct = "application/xml"
      self.assertFalse(detectRss(ct, xml))
      self.assertTrue(detectAtom(ct, xml))

    def test_RSSFromContentType(self):
      xml = ET.fromstring(
              "<mystery></mystery>"
              )
      ct = "application/rss+xml"
      self.assertTrue(detectRss(ct, xml))
      self.assertFalse(detectAtom(ct, xml))

    def test_AtomFromContentType(self):
      xml = ET.fromstring(
              "<mystery></mystery>"
              )
      ct = "application/atom+xml"
      self.assertFalse(detectRss(ct, xml))
      self.assertTrue(detectAtom(ct, xml))

    def test_HTML(self):
      xml = ET.fromstring(
              "<html></html>"
              )
      ct = "text/html"
      self.assertFalse(detectRss(ct, xml))
      self.assertFalse(detectAtom(ct, xml))

class ModifyRssTest(unittest.TestCase):
    def test_title(self):
      xml = ET.fromstring(
              "<rss><channel><title>foo</title></channel></rss>"
              )
      ff = FilterFeed()
      modifyRss(xml, ff)
      self.assertEqual(xml.find(".//channel/title").text, "foo (filtered)")

    def test_remove(self):
      xml = ET.fromstring(
              "<rss><channel><title>asdf</title><item><title>foo</title></item></channel></rss>"
              )
      ff = FilterFeed(query_builder={
          "condition": "AND",
          "rules": [{
              "id": "X",
              "field": "title",
              "type": "string",
              "input": "text",
              "operator": "equal",
              "value": "foo"
              }]})
      modifyRss(xml, ff)
      self.assertIsNone(xml.find(".//item/title"))
      self.assertIsNotNone(xml.find(".//channel/title"), "Accidentally removed title")

    def test_keep(self):
      xml = ET.fromstring(
              "<rss><channel><title>asdf</title><item><title>foo</title></item></channel></rss>"
              )
      ff = FilterFeed(query_builder={
          "condition": "AND",
          "rules": [{
              "id": "X",
              "field": "title",
              "type": "string",
              "input": "text",
              "operator": "equal",
              "value": "bar"
              }]})
      modifyRss(xml, ff)
      self.assertIsNotNone(xml.find(".//item/title"))
      self.assertIsNotNone(xml.find(".//channel/title"), "Accidentally removed title")


    def test_golden(self):
      xml_in = ET.parse("testdata/rss.xml")
      xml_check = ET.parse("testdata/rss-filtered.xml")
      ff = FilterFeed(query_builder={
          "condition": "AND",
          "rules": [{
              "id": "X",
              "field": "title",
              "type": "string",
              "input": "text",
              "operator": "contains",
              "value": "Boring"
              }]})
      modifyRss(xml_in.getroot(), ff)
      self.assertEqual(ET.tostring(xml_in.getroot()), ET.tostring(xml_check.getroot()))

