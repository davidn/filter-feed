
import unittest
import xml.etree.ElementTree as ET

from main import detectRss, detectAtom, modifyRss, modifyAtom

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
