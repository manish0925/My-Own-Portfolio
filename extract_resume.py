import PyPDF2

pdf = PyPDF2.PdfReader('static/Manish_Kushwaha_Resume.pdf')
text = ''
for page in pdf.pages:
    text += page.extract_text()
print(text[:2000])