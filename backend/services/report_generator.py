import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from database import get_db_connection
from datetime import datetime

class NumberedCanvas(canvas.Canvas):
    """
    Custom canvas to enable two-pass page numbering 
    (e.g., 'Page X of Y') and modern headers/footers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        # Primary Brand Color: Slate Blue
        brand_color = colors.HexColor("#4f46e5")
        text_color = colors.HexColor("#64748b")
        
        # Header (Top of every page except first)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(brand_color)
            self.drawString(54, 750, "AI VIRTUAL HR INTERVIEWER")
            self.setFont("Helvetica", 8)
            self.setFillColor(text_color)
            self.drawRightString(558, 750, "PERFORMANCE ASSESSMENT REPORT")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
            
        # Footer (Bottom of every page)
        self.setFont("Helvetica", 8)
        self.setFillColor(text_color)
        self.drawString(54, 36, "Confidential - AI Interview Feedback Report")
        self.drawRightString(558, 36, f"Page {self._pageNumber} of {page_count}")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        
        self.restoreState()

def generate_pdf_report(db_path, interview_id, output_path):
    """
    Queries the DB for interview session details and writes a stylized PDF report.
    """
    # 1. Fetch data from Database connection (SQLite or MySQL dynamically)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch interview details
    cursor.execute('''
        SELECT i.*, u.name as candidate_name, u.email as candidate_email 
        FROM interviews i 
        JOIN users u ON i.user_id = u.id 
        WHERE i.id = ?
    ''', (interview_id,))
    interview = cursor.fetchone()
    
    if not interview:
        conn.close()
        return False
        
    # Fetch responses details
    cursor.execute('''
        SELECT r.*, q.question_text, q.keywords, q.ideal_answer 
        FROM responses r
        JOIN questions q ON r.question_id = q.id 
        WHERE r.interview_id = ?
        ORDER BY r.id ASC
    ''', (interview_id,))
    responses = cursor.fetchall()
    conn.close()
    
    # 2. Setup ReportLab Document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=60
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Palette Styling
    primary_color = colors.HexColor("#1e1b4b")  # Dark Navy
    accent_color = colors.HexColor("#4f46e5")   # Indigo
    success_color = colors.HexColor("#10b981")  # Emerald
    warning_color = colors.HexColor("#f59e0b")  # Amber
    dark_gray = colors.HexColor("#334155")
    light_gray = colors.HexColor("#f8fafc")
    
    # Define custom typography styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=primary_color,
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=accent_color,
        spaceAfter=25
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=primary_color,
        spaceBefore=15,
        spaceAfter=10,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=dark_gray,
        spaceAfter=8
    )
    
    bold_body_style = ParagraphStyle(
        'BodyBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    table_text_style = ParagraphStyle(
        'TableText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=dark_gray
    )
    
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=table_text_style,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )
    
    story = []
    
    # --- PAGE 1: TITLE & EXECUTIVE SUMMARY ---
    # Decorative colored bar
    d_table = Table([['']], colWidths=[504], rowHeights=[4])
    d_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), accent_color),
        ('PADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(d_table)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("AI Virtual HR Interviewer", title_style))
    story.append(Paragraph("CANDIDATE PERFORMANCE ASSESSMENT REPORT", subtitle_style))
    
    # Candidate & Session Information Table
    info_data = [
        [Paragraph("Candidate Name:", bold_body_style), Paragraph(interview['candidate_name'], body_style),
         Paragraph("Interview Date:", bold_body_style), Paragraph(datetime.strptime(interview['created_at'], '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y %I:%M %p') if ' ' in interview['created_at'] else interview['created_at'], body_style)],
        [Paragraph("Email Address:", bold_body_style), Paragraph(interview['candidate_email'], body_style),
         Paragraph("Category:", bold_body_style), Paragraph(f"{interview['category']} Mock Interview", body_style)],
        [Paragraph("Overall Score:", bold_body_style), Paragraph(f"<b>{interview['overall_score']}%</b>", body_style),
         Paragraph("Session Status:", bold_body_style), Paragraph(interview['status'].capitalize(), body_style)]
    ]
    info_table = Table(info_data, colWidths=[100, 150, 100, 154])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (-1,-1), light_gray),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#e2e8f0")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Score Breakdown Section
    story.append(Paragraph("Score Breakdown", h1_style))
    
    # Scores Grid Table
    score_headers = [Paragraph("Metric", table_header_style), Paragraph("Score", table_header_style), Paragraph("Rating", table_header_style)]
    
    def get_rating(val):
        if val >= 85: return Paragraph("Excellent", ParagraphStyle('Green', parent=table_text_style, textColor=success_color, fontName='Helvetica-Bold'))
        if val >= 70: return Paragraph("Proficient", ParagraphStyle('Amber', parent=table_text_style, textColor=warning_color, fontName='Helvetica-Bold'))
        return Paragraph("Needs Improvement", ParagraphStyle('Red', parent=table_text_style, textColor=colors.red, fontName='Helvetica-Bold'))
        
    score_data = [
        score_headers,
        [Paragraph("Technical Competence", table_text_style), Paragraph(f"{interview['technical_score']}%", table_text_style), get_rating(interview['technical_score'])],
        [Paragraph("Communication Skills", table_text_style), Paragraph(f"{interview['communication_score']}%", table_text_style), get_rating(interview['communication_score'])],
        [Paragraph("Confidence & Pacing", table_text_style), Paragraph(f"{interview['confidence_score']}%", table_text_style), get_rating(interview['confidence_score'])],
        [Paragraph("Eye Contact & Engagement", table_text_style), Paragraph(f"{interview['eye_contact_score']}%", table_text_style), get_rating(interview['eye_contact_score'])],
        [Paragraph("<b>OVERALL PERFORMANCE</b>", table_text_style), Paragraph(f"<b>{interview['overall_score']}%</b>", table_text_style), get_rating(interview['overall_score'])]
    ]
    
    score_table = Table(score_data, colWidths=[200, 100, 204])
    score_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#e2e8f0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_gray]),
        ('LINEBELOW', (0,-1), (-1,-1), 1.5, primary_color)
    ]))
    story.append(score_table)
    story.append(Spacer(1, 20))
    
    # Executive Summary Feedback
    story.append(Paragraph("Executive Summary & Feedback", h1_style))
    summary_text = interview['feedback_summary'] if interview['feedback_summary'] else "Assessment completed successfully. The candidate showed solid participation. Refer below for question-specific insights."
    story.append(Paragraph(summary_text, body_style))
    
    story.append(PageBreak())
    
    # --- PAGE 2+: QUESTION BY QUESTION ASSESSMENT ---
    story.append(Paragraph("Detailed Question-by-Question Analysis", h1_style))
    
    for idx, resp in enumerate(responses):
        q_header_style = ParagraphStyle(
            f'QHeader_{idx}',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=14,
            textColor=accent_color,
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True
        )
        
        q_elements = [
            Paragraph(f"Question {idx + 1}: {resp['question_text']}", q_header_style),
            Spacer(1, 4)
        ]
        
        # Details Table for this response
        # Extract emotions and keywords
        kw_text = f"<b>Matched:</b> {resp['transcript']}" if resp['transcript'] else "No transcript available."
        
        resp_details = [
            [Paragraph("<b>Candidate Response:</b>", table_text_style), Paragraph(resp['transcript'] if resp['transcript'] else "<i>[No speech detected]</i>", table_text_style)],
            [Paragraph("<b>Technical Keywords:</b>", table_text_style), Paragraph(f"Keywords expected: {resp['keywords']}<br/>Matched: <i>{', '.join(resp['transcript'].lower().split()) if resp['transcript'] else 'none'}</i>", table_text_style)],
            [Paragraph("<b>Speaking Rate:</b>", table_text_style), Paragraph(f"{resp['speaking_speed']} Words Per Minute (WPM)", table_text_style)],
            [Paragraph("<b>Engagement Parameters:</b>", table_text_style), Paragraph(f"Eye Contact: {resp['eye_contact_ratio']}% | Confidence Score: {resp['confidence_score']}%", table_text_style)],
            [Paragraph("<b>AI Recommendation:</b>", table_text_style), Paragraph(resp['feedback'] if resp['feedback'] else "No specific suggestions.", table_text_style)]
        ]
        
        detail_table = Table(resp_details, colWidths=[130, 374])
        detail_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ('BACKGROUND', (0,0), (-1,-1), colors.white),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#f1f5f9")),
        ]))
        
        q_elements.append(detail_table)
        q_elements.append(Spacer(1, 15))
        
        # Keep each question block together to avoid page orphan splits
        story.append(KeepTogether(q_elements))
        
    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    return True
