"""Real capped PDF/DOCX workers; runs on Linux and native Windows CI."""
import base64
import io
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/core'))
from fastapi import HTTPException
from pypdf import PdfWriter
from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject
import document_extraction as extraction

def pdf(text='Source says PostgreSQL.',pages=1,encrypted=False):
    writer=PdfWriter()
    for _ in range(pages):
        page=writer.add_blank_page(width=300,height=200)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream=DecodedStreamObject();stream.set_data(('BT /F1 12 Tf 20 100 Td ('+text+') Tj ET').encode())
        page[NameObject('/Contents')]=writer._add_object(stream)
    if encrypted:writer.encrypt('not-a-test-secret')
    out=io.BytesIO();writer.write(out);return out.getvalue()

def docx(xml=None,extra=None):
    if xml is None:xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Préférences: kreyòl ayisyen.</w:t></w:r></w:p><w:p><w:r><w:t>Second paragraph.</w:t></w:r></w:p></w:body></w:document>'
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml','<Types/>');archive.writestr('word/document.xml',xml)
        if extra:
            for name,content in extra.items():archive.writestr(name,content)
    return out.getvalue()

def xlsx(reference='A1',all_hidden=False):
    out=io.BytesIO()
    namespace='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml','<Types/>')
        state='hidden' if all_hidden else 'visible'
        archive.writestr('xl/workbook.xml',f'<workbook xmlns="{namespace}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Visible" sheetId="1" r:id="r1" state="{state}"/><sheet name="Hidden" sheetId="2" r:id="r2" state="hidden"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Target="worksheets/sheet1.xml"/><Relationship Id="r2" Target="worksheets/sheet2.xml"/></Relationships>')
        archive.writestr('xl/sharedStrings.xml',f'<sst xmlns="{namespace}"><si><t>Préférences: kreyòl.</t></si></sst>')
        archive.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="{namespace}"><sheetData><row r="1"><c r="{reference}" t="s"><v>0</v></c><c r="B1"><v>7</v></c><c r="C1"><f>1+2</f><v>999</v></c></row></sheetData></worksheet>')
        archive.writestr('xl/worksheets/sheet2.xml',f'<worksheet xmlns="{namespace}"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Hidden sensitive text</t></is></c></row></sheetData></worksheet>')
    return out.getvalue()

def request(raw,kind):return extraction.ExtractRequest(kind=kind,data=base64.b64encode(raw).decode(),confirmed=True)

class DocumentExtraction(unittest.TestCase):
    def test_pdf_worker_extracts_real_text_and_source_hash(self):
        result=extraction.extract_selected(request(pdf(),'pdf'))
        self.assertIn('Source says PostgreSQL.',result['content']);self.assertIn('[PDF page 1]',result['content'])
        self.assertEqual(result['diagnostics']['pages'],1);self.assertFalse(result['diagnostics']['ocr'])
        self.assertFalse(result['binary_stored']);self.assertEqual(len(result['source_sha256']),64)
        self.assertEqual(result['worker_limits']['memory_bytes'],256*1024*1024)
    def test_docx_worker_preserves_accents_paragraphs_and_limits(self):
        result=extraction.extract_selected(request(docx(),'docx'))
        self.assertIn('Préférences: kreyòl ayisyen.',result['content']);self.assertIn('\nSecond paragraph.',result['content'])
        self.assertEqual(result['diagnostics']['paragraphs'],2)
        self.assertIn(result['worker_limits']['platform'],{'unix_rlimit','windows_job'})
    def test_encrypted_too_many_pages_invalid_and_empty_pdf_are_rejected(self):
        for raw in [pdf(encrypted=True),pdf(pages=26),b'%PDF-broken',pdf(text='')]:
            with self.assertRaises(HTTPException) as caught:extraction.extract_selected(request(raw,'pdf'))
            self.assertEqual(caught.exception.status_code,422)
    def test_docx_entities_paths_embedded_binary_and_expansion_are_rejected(self):
        for raw in [docx(xml='<!DOCTYPE x [<!ENTITY sample "bad">]><x>&sample;</x>'),
                    docx(extra={'../escape':'bad'}),docx(extra={'word/vbaProject.bin':'bad'}),
                    docx(extra={'word/large.xml':'x'*(2*1024*1024+1)}),b'broken ZIP']:
            with self.assertRaises(HTTPException) as caught:extraction.extract_selected(request(raw,'docx'))
            self.assertEqual(caught.exception.status_code,422)
    def test_xlsx_worker_reads_cells_but_never_evaluates_formulas_or_hidden_sheets(self):
        result=extraction.extract_selected(request(xlsx(),'xlsx'))
        self.assertIn('A1=Préférences: kreyòl.',result['content']);self.assertIn('B1=7',result['content'])
        self.assertIn('[Formula not evaluated: 1+2; cached value: 999]',result['content'])
        self.assertNotIn('Hidden sensitive text',result['content'])
        self.assertEqual(result['diagnostics']['hidden_sheets_omitted'],1)
        self.assertEqual(result['diagnostics']['formulas_not_evaluated'],1)
        self.assertFalse(result['diagnostics']['cached_values_verified'])
        for raw in [xlsx(reference='AY1'),xlsx(all_hidden=True)]:
            with self.assertRaises(HTTPException) as caught:extraction.extract_selected(request(raw,'xlsx'))
            self.assertEqual(caught.exception.status_code,422)
    def test_extraction_api_never_stores_binary_and_requires_confirmation(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import documents
        app=FastAPI();app.include_router(documents.router);app.add_middleware(documents.DocumentBodyLimit)
        client=TestClient(app)
        with patch.object(documents.memory,'connect',side_effect=AssertionError('Extraction must not access document storage')):
            body=request(pdf(),'pdf').model_dump()
            response=client.post('/documents/extract',json=body)
            self.assertEqual(response.status_code,200,response.text);self.assertFalse(response.json()['binary_stored'])
            self.assertEqual(client.post('/documents/extract',json={**body,'confirmed':1}).status_code,422)
            self.assertEqual(client.post('/documents/extract',content=b'x'*(2*1024*1024+1)).status_code,413)
    def test_timeout_kills_worker_and_uses_a_fixed_isolated_command(self):
        import subprocess
        from unittest.mock import MagicMock
        process=MagicMock();process.communicate.side_effect=[subprocess.TimeoutExpired('fixed-worker',10),(b'',None)]
        process.poll.return_value=-9
        with patch.object(extraction.subprocess,'Popen',return_value=process) as spawn, \
             patch.object(extraction,'_windows_job',return_value=lambda:None):
            with self.assertRaises(HTTPException) as caught:extraction.extract_selected(request(pdf(),'pdf'))
            self.assertEqual(caught.exception.status_code,422);process.kill.assert_called_once()
            args,kwargs=spawn.call_args
            self.assertEqual(args[0][0:2],[sys.executable,'-I']);self.assertTrue(args[0][2].endswith('document_worker.py'))
            self.assertFalse(kwargs['shell']);self.assertNotIn('DATABASE_URL',kwargs['env']);self.assertNotIn('PYTHONPATH',kwargs['env'])
    def test_strict_confirmation_base64_limits_and_busy_slot(self):
        for fields in [dict(confirmed=1),dict(confirmed=False),dict(data='invalid!'),dict(kind='doc'),
                       dict(data=base64.b64encode(b'x'*(1024*1024+1)).decode()),dict(path='/private')]:
            body=dict(kind='pdf',data=base64.b64encode(b'x').decode(),confirmed=True);body.update(fields)
            with self.assertRaises(ValueError):extraction.ExtractRequest(**body)
        with patch.object(extraction,'_slots') as slots:
            slots.acquire.return_value=False
            with self.assertRaises(HTTPException) as caught:extraction.extract_selected(request(pdf(),'pdf'))
            self.assertEqual(caught.exception.status_code,429);slots.release.assert_not_called()

if __name__=='__main__':unittest.main()
