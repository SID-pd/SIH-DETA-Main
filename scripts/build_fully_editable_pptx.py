import base64
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor

ASSETS_DIR = Path(r"c:\Users\Asus\Coding\SIH\ETA\scratch\pptx_assets")
OUT_PPTX = Path(r"c:\Users\Asus\Coding\SIH\ETA\SIH2026-DARPAN-Twarit-SIH26028.pptx")

# CSS Pixel to PowerPoint Inches (1280x720 -> 13.333x7.5 in widescreen)
def px(v):
    return Inches(v / 96.0)

# CSS Pixel to Point size (1 px = 0.75 pt)
def fpt(px_val):
    return Pt(px_val * 0.75)

# Fonts
FONT_SERIF = "Georgia"
FONT_SANS = "Segoe UI"
FONT_MONO = "Consolas"

# Palette matching SIH Design System
C_NAVY_DARK   = RGBColor(17, 42, 70)      # #112a46
C_NAVY_MED    = RGBColor(23, 63, 112)     # #173f70
C_NAVY_TEXT   = RGBColor(15, 23, 42)      # #0f172a
C_BLUE_BRAND  = RGBColor(12, 102, 180)    # #0c66b4 footer
C_BLUE_ACCENT = RGBColor(37, 99, 235)     # #2563eb
C_BLUE_LINK   = RGBColor(29, 78, 216)     # #1d4ed8
C_BLUE_BG     = RGBColor(239, 246, 255)   # #eff6ff
C_GREEN_DARK  = RGBColor(21, 128, 61)     # #15803d
C_GREEN_BG    = RGBColor(240, 253, 244)   # #f0fdf4
C_RED_DARK    = RGBColor(185, 28, 28)     # #b91c1c
C_RED_BG      = RGBColor(254, 242, 242)   # #fef2f2
C_PURPLE      = RGBColor(89, 56, 118)     # #593876
C_TEAL        = RGBColor(31, 121, 140)    # #1f798c
C_AMBER       = RGBColor(217, 119, 6)     # #d97706
C_AMBER_BG    = RGBColor(255, 251, 235)   # #fffbeb
C_GRAY_BG     = RGBColor(241, 243, 245)   # #f1f3f5
C_GRAY_CARD   = RGBColor(248, 250, 252)   # #f8fafc
C_BORDER_GRAY = RGBColor(203, 213, 225)   # #cbd5e1
C_WHITE       = RGBColor(255, 255, 255)


def add_common_decorations(slide, title_text, page_num, subtitle_text=None, title_font_size=34):
    # 1. Oval Twarit Badge (top left)
    oval = slide.shapes.add_shape(MSO_SHAPE.OVAL, px(18), px(14), px(124), px(64))
    oval.fill.solid()
    oval.fill.fore_color.rgb = C_WHITE
    oval.line.color.rgb = RGBColor(92, 75, 139) # #5c4b8b
    oval.line.width = Pt(2.2)
    tf = oval.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Twarit"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = RGBColor(30, 41, 59)

    # 2. Top Right Official SIH Logo
    logo_path = ASSETS_DIR / "logo.png"
    if logo_path.exists():
        slide.shapes.add_picture(str(logo_path), px(1150), px(6), width=px(112), height=px(68))

    # 3. Slide Title & Optional Subtitle
    if title_text:
        t_top = px(10) if subtitle_text else px(14)
        t_h = px(36) if subtitle_text else px(50)
        tx = slide.shapes.add_textbox(px(145), t_top, px(990), t_h)
        tf = tx.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0)
        tf.margin_bottom = Inches(0)
        p = tf.paragraphs[0]
        p.text = title_text
        p.alignment = PP_ALIGN.CENTER
        p.font.name = FONT_SANS
        p.font.size = fpt(title_font_size)
        p.font.bold = True
        p.font.color.rgb = C_NAVY_TEXT

    if subtitle_text:
        sub_tx = slide.shapes.add_textbox(px(145), px(44), px(990), px(24))
        tf_sub = sub_tx.text_frame
        tf_sub.word_wrap = True
        tf_sub.margin_top = Inches(0)
        tf_sub.margin_bottom = Inches(0)
        p_sub = tf_sub.paragraphs[0]
        p_sub.text = subtitle_text
        p_sub.alignment = PP_ALIGN.CENTER
        p_sub.font.name = FONT_SANS
        p_sub.font.size = fpt(13.2)
        p_sub.font.bold = True
        p_sub.font.color.rgb = C_BLUE_ACCENT

    # 4. Footer Bar
    footer = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, px(0), px(686), px(1280), px(34))
    footer.fill.solid()
    footer.fill.fore_color.rgb = C_BLUE_BRAND
    footer.line.fill.background()
    tf = footer.text_frame
    tf.margin_top = Inches(0)
    tf.margin_bottom = Inches(0)
    p = tf.paragraphs[0]
    p.text = "@SIH Idea submission- Template"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.size = fpt(13.5)
    p.font.color.rgb = C_WHITE

    # Page number on footer
    pg_tx = slide.shapes.add_textbox(px(1200), px(686), px(60), px(34))
    tf2 = pg_tx.text_frame
    tf2.margin_top = Inches(0)
    tf2.margin_bottom = Inches(0)
    p2 = tf2.paragraphs[0]
    p2.text = str(page_num)
    p2.alignment = PP_ALIGN.CENTER
    p2.font.name = FONT_SANS
    p2.font.size = fpt(14)
    p2.font.bold = True
    p2.font.color.rgb = C_WHITE


# -------------------------------------------------------------
# SLIDE 1: Title, Problem Details, Engineering Split, Metrics
# -------------------------------------------------------------
def build_slide1(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # Hexagonal gray polygon behind emblem
    hex_shape = slide.shapes.add_shape(MSO_SHAPE.HEXAGON, px(480), px(130), px(380), px(440))
    hex_shape.fill.solid()
    hex_shape.fill.fore_color.rgb = C_GRAY_BG
    hex_shape.line.fill.background()

    # Logo
    logo_path = ASSETS_DIR / "logo.png"
    if logo_path.exists():
        slide.shapes.add_picture(str(logo_path), px(1150), px(10), width=px(112), height=px(78))

    # Brain emblem
    emblem_path = ASSETS_DIR / "emblem.png"
    if emblem_path.exists():
        slide.shapes.add_picture(str(emblem_path), px(575), px(200), width=px(210), height=px(240))

    # Main Title
    t_box = slide.shapes.add_textbox(px(0), px(22), px(1280), px(50))
    tf = t_box.text_frame
    tf.margin_top = Inches(0)
    tf.margin_bottom = Inches(0)
    p = tf.paragraphs[0]
    p.text = "SMART INDIA HACKATHON 2026"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SERIF
    p.font.size = fpt(41)
    p.font.bold = True
    p.font.color.rgb = C_NAVY_MED

    # DARPAN sub
    d_box = slide.shapes.add_textbox(px(0), px(70), px(1280), px(45))
    tf = d_box.text_frame
    tf.margin_top = Inches(0)
    tf.margin_bottom = Inches(0)
    p = tf.paragraphs[0]
    p.text = "DARPAN (SIH-DETA)"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.size = fpt(34)
    p.font.bold = True
    p.font.color.rgb = C_NAVY_TEXT

    # Banner
    b_shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(260), px(118), px(760), px(34))
    b_shape.fill.solid()
    b_shape.fill.fore_color.rgb = C_NAVY_MED
    b_shape.line.fill.background()
    tf = b_shape.text_frame
    tf.margin_top = Inches(0)
    tf.margin_bottom = Inches(0)
    p = tf.paragraphs[0]
    p.text = "Self-Growing Hybrid AI & Railway Physics Engine for Coaching Train ETA"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.size = fpt(17)
    p.font.bold = True
    p.font.color.rgb = C_WHITE

    # Left Bullets Box
    bul_box = slide.shapes.add_textbox(px(32), px(180), px(530), px(260))
    tf = bul_box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0)
    tf.margin_top = Inches(0)

    bullets = [
        ("Problem Statement ID – ", "SIH26028"),
        ("Problem Statement Title – ", "Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains"),
        ("Organization / Dept – ", "Ministry of Railways (MIC)"),
        ("Theme – ", "Smart Automation | Category – Software"),
        ("Team ID – ", "131076 | Team Name – Twarit"),
    ]
    for i, (lbl, val) in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        r1 = p.add_run()
        r1.text = "• " + lbl
        r1.font.name = FONT_SANS
        r1.font.bold = True
        r1.font.size = fpt(21)
        r1.font.color.rgb = C_NAVY_TEXT
        r2 = p.add_run()
        r2.text = val
        r2.font.name = FONT_SANS
        r2.font.bold = True
        r2.font.size = fpt(21)
        r2.font.color.rgb = C_NAVY_MED

    # Team Deliverables Card (Right)
    team_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(870), px(175), px(385), px(260))
    team_card.fill.solid()
    team_card.fill.fore_color.rgb = C_WHITE
    team_card.line.color.rgb = C_BORDER_GRAY
    team_card.line.width = Pt(1.5)

    # Top accent bar on team card
    t_top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, px(870), px(175), px(385), px(5))
    t_top_bar.fill.solid()
    t_top_bar.fill.fore_color.rgb = C_NAVY_MED
    t_top_bar.line.fill.background()

    # Header row inside Card: Label on left + 6-MEMBER SPLIT pill on right
    th_tx = slide.shapes.add_textbox(px(880), px(182), px(255), px(24))
    tf_th = th_tx.text_frame
    tf_th.margin_top = Inches(0)
    tf_th.margin_left = Inches(0)
    p = tf_th.paragraphs[0]
    p.text = "👥 TEAM TWARIT — ENGINEERING DELIVERABLES"
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(10.2)
    p.font.color.rgb = C_NAVY_MED

    pill_split = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(1150), px(184), px(95), px(20))
    pill_split.fill.solid()
    pill_split.fill.fore_color.rgb = C_GREEN_BG
    pill_split.line.color.rgb = RGBColor(187, 247, 208)
    tf_ps = pill_split.text_frame
    tf_ps.margin_top = Inches(0)
    tf_ps.margin_bottom = Inches(0)
    p = tf_ps.paragraphs[0]
    p.text = "6-MEMBER SPLIT"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_MONO
    p.font.bold = True
    p.font.size = fpt(9.5)
    p.font.color.rgb = C_GREEN_DARK

    roles_data = [
        ("Lead & Architect", C_NAVY_MED, [("2-Pass Hybrid Engine", True), (", Space-Time DAG & Zero-Clash Platform IntervalTree", False)]),
        ("AI / ML Lead", RGBColor(13, 148, 136), [("31-Feature Quantile GBDT", True), (" (P10/P50/P90) & Delay-Jump Classifier (0.92 AUC)", False)]),
        ("Data & Scraper", C_PURPLE, [("1.68 GB 6-DB Data Lake", True), (", 24x7 Failover Scraper & Feedback Scorer Loop", False)]),
        ("Backend & API", C_BLUE_LINK, [("FastAPI /v1/deta Gateway", True), (", <1.5ms Redis Cache & Manual Accident API", False)]),
        ("UI & Rail Ops", C_AMBER, [("React 18 + Leaflet GIS", True), (" (3 User Views), G&SR Fog/Heat Rules & 20K Backtest", False)]),
    ]
    for r_idx, (r_title, r_col, r_runs) in enumerate(roles_data):
        y_r = px(215 + r_idx * 42)
        # Left pill
        pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(880), y_r, px(112), px(22))
        pill.fill.solid()
        pill.fill.fore_color.rgb = r_col
        pill.line.fill.background()
        tf_p = pill.text_frame
        tf_p.margin_top = Inches(0)
        tf_p.margin_bottom = Inches(0)
        p = tf_p.paragraphs[0]
        p.text = r_title
        p.alignment = PP_ALIGN.CENTER
        p.font.name = FONT_SANS
        p.font.bold = True
        p.font.size = fpt(9.5)
        p.font.color.rgb = C_WHITE

        # Right description with bold highlights
        desc_tx = slide.shapes.add_textbox(px(1000), y_r - px(2), px(250), px(38))
        tf_d = desc_tx.text_frame
        tf_d.word_wrap = True
        tf_d.margin_top = Inches(0)
        tf_d.margin_left = Inches(0)
        p = tf_d.paragraphs[0]
        for txt, is_b in r_runs:
            run = p.add_run()
            run.text = txt
            run.font.name = FONT_SANS
            run.font.bold = is_b
            run.font.size = fpt(10.8)
            run.font.color.rgb = C_NAVY_TEXT

    # Bottom Metric Strip
    met_strip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(32), px(630), px(1220), px(58))
    met_strip.fill.solid()
    met_strip.fill.fore_color.rgb = C_WHITE
    met_strip.line.color.rgb = C_BORDER_GRAY
    met_strip.line.width = Pt(1.5)

    # Accent blue left border
    accent_bar = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(32), px(630), px(6), px(58))
    accent_bar.fill.solid()
    accent_bar.fill.fore_color.rgb = C_NAVY_MED
    accent_bar.line.fill.background()

    metrics = [
        ("1.68 GB (Self-Growing)", "6-DB Live Scraping & Feedback Lake"),
        ("8,990 Stns · 704 Cabins", "417,080 Schedule Stops Mapped"),
        ("1.51M Delays · 3.19M Wx", "73,342 Track Recovery Profiles"),
        ("4.93m ➔ 1.49m (-70%)", "Typical Error Cut (N=20,000 Test)"),
        ("85.3% Window + Manual Ops", "P10–P90 Band + Live Accident Input"),
    ]
    for i, (m_val, m_lbl) in enumerate(metrics):
        # Subtle vertical divider line
        if i > 0:
            div = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, px(42 + i * 242), px(638), px(1), px(42))
            div.fill.solid()
            div.fill.fore_color.rgb = RGBColor(226, 232, 240)
            div.line.fill.background()

        tx = slide.shapes.add_textbox(px(46 + i * 242), px(633), px(236), px(52))
        tf = tx.text_frame
        tf.margin_top = Inches(0)
        tf.margin_left = Inches(0)
        p = tf.paragraphs[0]
        p.text = m_val
        p.font.name = FONT_MONO
        p.font.bold = True
        p.font.size = fpt(16)
        p.font.color.rgb = C_NAVY_MED
        p2 = tf.add_paragraph()
        p2.text = m_lbl
        p2.font.name = FONT_SANS
        p2.font.bold = True
        p2.font.size = fpt(10.5)
        p2.font.color.rgb = RGBColor(71, 85, 105)


# -------------------------------------------------------------
# SLIDE 2: DARPAN Core Idea, Solution Mindmap & Uniqueness
# -------------------------------------------------------------
def build_slide2(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_common_decorations(
        slide,
        "DARPAN",
        2,
        subtitle_text="(Dynamic Forecast of Expected Time of Arrival for Coaching Trains — SIH26028)",
        title_font_size=33
    )

    # GIST Box with Left Blue Accent
    gist = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(32), px(66), px(1216), px(34))
    gist.fill.solid()
    gist.fill.fore_color.rgb = RGBColor(248, 250, 252)
    gist.line.color.rgb = C_BORDER_GRAY
    gist.line.width = Pt(1.5)

    gist_bar = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(32), px(66), px(5), px(34))
    gist_bar.fill.solid()
    gist_bar.fill.fore_color.rgb = C_NAVY_MED
    gist_bar.line.fill.background()

    tf = gist.text_frame
    tf.word_wrap = True
    tf.margin_top = Inches(0.03)
    tf.margin_left = Inches(0.12)
    p = tf.paragraphs[0]
    r1 = p.add_run()
    r1.text = "GIST: "
    r1.font.name = FONT_SANS
    r1.font.bold = True
    r1.font.size = fpt(13.2)
    r1.font.color.rgb = C_NAVY_MED

    r2 = p.add_run()
    r2.text = "Replaces Indian Railways' static "
    r2.font.name = FONT_SANS
    r2.font.size = fpt(12.8)
    r2.font.color.rgb = C_NAVY_TEXT

    r3 = p.add_run()
    r3.text = "Schedule + Current Delay - Fixed Buffer"
    r3.font.name = FONT_MONO
    r3.font.bold = True
    r3.font.size = fpt(11.5)
    r3.font.color.rgb = C_BLUE_LINK

    r4 = p.add_run()
    r4.text = " formula with a "
    r4.font.name = FONT_SANS
    r4.font.size = fpt(12.8)
    r4.font.color.rgb = C_NAVY_TEXT

    r5 = p.add_run()
    r5.text = "Self-Growing Hybrid AI + Railway Physics Engine"
    r5.font.name = FONT_SANS
    r5.font.bold = True
    r5.font.size = fpt(12.8)
    r5.font.color.rgb = C_NAVY_TEXT

    r6 = p.add_run()
    r6.text = " that predicts "
    r6.font.name = FONT_SANS
    r6.font.size = fpt(12.8)
    r6.font.color.rgb = C_NAVY_TEXT

    r7 = p.add_run()
    r7.text = "Best / Expected / Worst-Case arrival windows (P10/P50/P90)"
    r7.font.name = FONT_SANS
    r7.font.bold = True
    r7.font.size = fpt(12.8)
    r7.font.color.rgb = C_GREEN_DARK

    r8 = p.add_run()
    r8.text = " & supports "
    r8.font.name = FONT_SANS
    r8.font.size = fpt(12.8)
    r8.font.color.rgb = C_NAVY_TEXT

    r9 = p.add_run()
    r9.text = "live manual accident overrides."
    r9.font.name = FONT_SANS
    r9.font.bold = True
    r9.font.size = fpt(12.8)
    r9.font.color.rgb = C_NAVY_TEXT

    col_w = px(392)
    col_h = px(538)
    col_y = px(118)

    # Column 1: Core Idea
    col1 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(32), col_y, col_w, col_h)
    col1.fill.solid()
    col1.fill.fore_color.rgb = C_WHITE
    col1.line.color.rgb = C_BORDER_GRAY
    col1.line.width = Pt(1.5)

    # Top Lightbulb icon circle
    ic1 = slide.shapes.add_shape(MSO_SHAPE.OVAL, px(213), col_y - px(15), px(30), px(30))
    ic1.fill.solid()
    ic1.fill.fore_color.rgb = C_WHITE
    ic1.line.color.rgb = C_NAVY_MED
    ic1.line.width = Pt(1.5)
    tf_ic1 = ic1.text_frame
    tf_ic1.margin_top = Inches(0)
    tf_ic1.margin_bottom = Inches(0)
    p = tf_ic1.paragraphs[0]
    p.text = "💡"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(13)

    hdr1 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(42), col_y + px(16), px(372), px(28))
    hdr1.fill.solid()
    hdr1.fill.fore_color.rgb = C_NAVY_MED
    hdr1.line.fill.background()
    p = hdr1.text_frame.paragraphs[0]
    p.text = "Core Idea (How It Works)"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(14)
    p.font.color.rgb = C_WHITE

    items1 = [
        ("2-Step Hybrid Engine (AI + Rail Rules):", [
            ("Step 1 predicts travel drift via ", False),
            ("31-Feature Gradient Boosted AI", True),
            (" [P10/P50/P90]", True, C_BLUE_LINK, FONT_MONO),
            ("; Step 2 enforces track & platform physics ", False),
            ("[Space-Time DAG]", True, C_BLUE_LINK, FONT_MONO),
            (".", False),
        ]),
        ("Smart-Zoom Route Tracking:", [
            ("Runs fast ", False),
            ("station-to-station", True),
            (" [O(1) Mode]", True, C_BLUE_LINK, FONT_MONO),
            (" when on time; zooms into ", False),
            ("halt-by-halt signal cabins", True),
            (" [704 Cabins]", True, C_BLUE_LINK, FONT_MONO),
            (" when delayed.", False),
        ]),
        ("Self-Growing DB & Feedback Flywheel:", [
            ("Constantly scrapes live runs & scores its own past predictions ", False),
            ("[1.68 GB now]", True, C_BLUE_LINK, FONT_MONO),
            ("—the longer it runs, the smarter & more ", False),
            ("accurate it gets.", True),
        ]),
        ("Manual Unpredicted Accident Input:", [
            ("Control rooms can inject ", False),
            ("sudden unpredicted accidents/blocks", True),
            (" [1-Click Override]", True, C_AMBER, FONT_MONO),
            (" to instantly recompute ETAs & 25kV detours.", False),
        ]),
    ]
    for idx, (title, runs) in enumerate(items1):
        card_y = col_y + px(50 + idx * 120)
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(42), card_y, px(372), px(114))
        card.fill.solid()
        card.fill.fore_color.rgb = C_GRAY_CARD
        card.line.color.rgb = C_BORDER_GRAY

        badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, px(48), card_y + px(8), px(22), px(22))
        badge.fill.solid()
        badge.fill.fore_color.rgb = C_NAVY_MED
        badge.line.fill.background()
        tf_b = badge.text_frame
        tf_b.margin_top = Inches(0)
        tf_b.margin_bottom = Inches(0)
        p_b = tf_b.paragraphs[0]
        p_b.text = str(idx + 1)
        p_b.alignment = PP_ALIGN.CENTER
        p_b.font.name = FONT_SANS
        p_b.font.bold = True
        p_b.font.size = fpt(11)
        p_b.font.color.rgb = C_WHITE

        tx = slide.shapes.add_textbox(px(76), card_y + px(4), px(332), px(106))
        tf = tx.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0)
        tf.margin_left = Inches(0)
        p = tf.paragraphs[0]
        r1 = p.add_run()
        r1.text = title + " "
        r1.font.name = FONT_SANS
        r1.font.bold = True
        r1.font.size = fpt(11.8)
        r1.font.color.rgb = C_NAVY_MED

        for r_spec in runs:
            r_txt = r_spec[0]
            r_bold = r_spec[1]
            r_col = r_spec[2] if len(r_spec) > 2 else C_NAVY_TEXT
            r_font = r_spec[3] if len(r_spec) > 3 else FONT_SANS
            run = p.add_run()
            run.text = r_txt
            run.font.name = r_font
            run.font.bold = r_bold
            run.font.size = fpt(11.2)
            run.font.color.rgb = r_col

    # Column 2: Problem Resolution
    col2 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(444), col_y, col_w, col_h)
    col2.fill.solid()
    col2.fill.fore_color.rgb = C_WHITE
    col2.line.color.rgb = C_BORDER_GRAY
    col2.line.width = Pt(1.5)

    # Top Target icon circle
    ic2 = slide.shapes.add_shape(MSO_SHAPE.OVAL, px(625), col_y - px(15), px(30), px(30))
    ic2.fill.solid()
    ic2.fill.fore_color.rgb = C_WHITE
    ic2.line.color.rgb = C_PURPLE
    ic2.line.width = Pt(1.5)
    tf_ic2 = ic2.text_frame
    tf_ic2.margin_top = Inches(0)
    tf_ic2.margin_bottom = Inches(0)
    p = tf_ic2.paragraphs[0]
    p.text = "🎯"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(13)

    hdr2 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(454), col_y + px(16), px(372), px(28))
    hdr2.fill.solid()
    hdr2.fill.fore_color.rgb = C_PURPLE
    hdr2.line.fill.background()
    p = hdr2.text_frame.paragraphs[0]
    p.text = "How We Solve Every PS Point"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(14)
    p.font.color.rgb = C_WHITE

    items2 = [
        ("Replaces Static Recovery Buffers:", [
            ("CAG audits show fixed buffers fail on ", False),
            (">100% congested trunk lines.", True),
            (" We learn real section slack & enforce ", False),
            ("no early departure before schedule", True),
            (" [STD Hold]", True, C_BLUE_LINK, FONT_MONO),
            (".", False),
        ]),
        ("Overtaking & Following-Train Delays:", [
            ("Models ", False),
            ("Vande Bharat / Rajdhani priority overtaking", True),
            (" [COA 6-Tier]", True, C_BLUE_LINK, FONT_MONO),
            (" and ", False),
            ("3–7 min safety headway gaps", True),
            (" behind slower trains.", False),
        ]),
        ("Official Fog, Rain & Track-Heat Rules:", [
            ("Converts live weather into ", False),
            ("Indian Railways G&SR Fog-Pass speed limits", True),
            (" [75/60/30 km/h]", True, C_BLUE_LINK, FONT_MONO),
            (" & ", False),
            ("60°C rail-buckling", True),
            (" speed caps.", False),
        ]),
        ("Zero-Clash Platforms & Crowd Surges:", [
            ("[IntervalTree]", True, C_BLUE_LINK, FONT_MONO),
            (" prevents platform clashes, predicts ", False),
            ("Outer Home Signal wait times", True),
            (", and models ", False),
            ("Festival Crowd Halts (Maha Kumbh 3.2x).", True),
        ]),
    ]
    for idx, (title, runs) in enumerate(items2):
        card_y = col_y + px(50 + idx * 120)
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(454), card_y, px(372), px(114))
        card.fill.solid()
        card.fill.fore_color.rgb = C_GRAY_CARD
        card.line.color.rgb = C_BORDER_GRAY

        badge = slide.shapes.add_shape(MSO_SHAPE.OVAL, px(460), card_y + px(8), px(22), px(22))
        badge.fill.solid()
        badge.fill.fore_color.rgb = C_PURPLE
        badge.line.fill.background()
        tf_b = badge.text_frame
        tf_b.margin_top = Inches(0)
        tf_b.margin_bottom = Inches(0)
        p_b = tf_b.paragraphs[0]
        p_b.text = str(idx + 1)
        p_b.alignment = PP_ALIGN.CENTER
        p_b.font.name = FONT_SANS
        p_b.font.bold = True
        p_b.font.size = fpt(11)
        p_b.font.color.rgb = C_WHITE

        tx = slide.shapes.add_textbox(px(488), card_y + px(4), px(332), px(106))
        tf = tx.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0)
        tf.margin_left = Inches(0)
        p = tf.paragraphs[0]
        r1 = p.add_run()
        r1.text = title + " "
        r1.font.name = FONT_SANS
        r1.font.bold = True
        r1.font.size = fpt(11.8)
        r1.font.color.rgb = C_PURPLE

        for r_spec in runs:
            r_txt = r_spec[0]
            r_bold = r_spec[1]
            r_col = r_spec[2] if len(r_spec) > 2 else C_NAVY_TEXT
            r_font = r_spec[3] if len(r_spec) > 3 else FONT_SANS
            run = p.add_run()
            run.text = r_txt
            run.font.name = r_font
            run.font.bold = r_bold
            run.font.size = fpt(11.2)
            run.font.color.rgb = r_col

    # Column 3: Mindmap & Results
    col3 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(856), col_y, col_w, col_h)
    col3.fill.solid()
    col3.fill.fore_color.rgb = C_WHITE
    col3.line.color.rgb = C_BORDER_GRAY
    col3.line.width = Pt(1.5)

    # Top Trophy icon circle
    ic3 = slide.shapes.add_shape(MSO_SHAPE.OVAL, px(1037), col_y - px(15), px(30), px(30))
    ic3.fill.solid()
    ic3.fill.fore_color.rgb = C_WHITE
    ic3.line.color.rgb = C_TEAL
    ic3.line.width = Pt(1.5)
    tf_ic3 = ic3.text_frame
    tf_ic3.margin_top = Inches(0)
    tf_ic3.margin_bottom = Inches(0)
    p = tf_ic3.paragraphs[0]
    p.text = "🏆"
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(13)

    hdr3 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(866), col_y + px(16), px(372), px(28))
    hdr3.fill.solid()
    hdr3.fill.fore_color.rgb = C_TEAL
    hdr3.line.fill.background()
    p = hdr3.text_frame.paragraphs[0]
    p.text = "Core Architecture Mindmap & Results"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(14)
    p.font.color.rgb = C_WHITE

    # 1. Clean Mindmap Box Image
    mm_path = ASSETS_DIR / "mindmap_card.png"
    if mm_path.exists():
        slide.shapes.add_picture(str(mm_path), px(866), col_y + px(50), width=px(372), height=px(180))

    # 2. Accuracy Card (Green highlight container matching HTML)
    acc_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(866), col_y + px(236), px(372), px(60))
    acc_card.fill.solid()
    acc_card.fill.fore_color.rgb = C_GREEN_BG
    acc_card.line.color.rgb = RGBColor(134, 239, 172)
    tf = acc_card.text_frame
    tf.word_wrap = True
    tf.margin_top = Inches(0.04)
    tf.margin_left = Inches(0.08)
    p = tf.paragraphs[0]
    r1 = p.add_run()
    r1.text = "✓ 85.3% Window Accuracy & 0.92 AUC: "
    r1.font.name = FONT_SANS
    r1.font.bold = True
    r1.font.size = fpt(11.8)
    r1.font.color.rgb = C_GREEN_DARK

    r2 = p.add_run()
    r2.text = "Calibrated [P10, P90] arrival window band + "
    r2.font.name = FONT_SANS
    r2.font.size = fpt(11.2)
    r2.font.color.rgb = C_NAVY_TEXT

    r3 = p.add_run()
    r3.text = "Renamed Code Bridge"
    r3.font.name = FONT_SANS
    r3.font.bold = True
    r3.font.size = fpt(11.2)
    r3.font.color.rgb = C_NAVY_TEXT

    r4 = p.add_run()
    r4.text = " (+72.5K rows rescued)."
    r4.font.name = FONT_SANS
    r4.font.size = fpt(11.2)
    r4.font.color.rgb = C_NAVY_TEXT

    # 3. Held-Out Error Comparison Card Image
    ec_path = ASSETS_DIR / "error_chart_card.png"
    if ec_path.exists():
        slide.shapes.add_picture(str(ec_path), px(866), col_y + px(302), width=px(372), height=px(112))


# -------------------------------------------------------------
# SLIDE 3: Technical Approach & Data Flow Diagram (DFD)
# -------------------------------------------------------------
def build_slide3(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_common_decorations(slide, "TECHNICAL APPROACH & DATA FLOW DIAGRAM", 3)

    col_y = px(70)
    col_h = px(556)

    # Left Panel (width: 43%)
    left_w = px(530)
    left_panel = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(28), col_y, left_w, col_h)
    left_panel.fill.solid()
    left_panel.fill.fore_color.rgb = C_WHITE
    left_panel.line.color.rgb = C_BORDER_GRAY
    left_panel.line.width = Pt(1.5)

    l_hdr = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(38), col_y + px(8), px(510), px(26))
    l_hdr.fill.solid()
    l_hdr.fill.fore_color.rgb = C_NAVY_DARK
    l_hdr.line.fill.background()
    p = l_hdr.text_frame.paragraphs[0]
    p.text = "TECHNOLOGY STACK & TRAJECTORY FORECAST"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(13.2)
    p.font.color.rgb = C_WHITE

    tech_cards = [
        ("1. 24x7 Scraping & Weather Ingestion:", [
            ("4-Source Failover (ConfirmTkt➔NTES➔eRail) + Open-Meteo 180-Hex Grid + ", False),
            ("Smart Pacing (-79.9% load).", True),
        ]),
        ("2. Self-Growing 6-Database Lake (1.68 GB+):", [
            ("6 SQLite DBs (darpan, historical, weather, stations, telemetry, anomalies) + ", False),
            ("<1.5ms Cache.", True),
        ]),
        ("3. Layer 1 — 31 G&SR Operational Features:", [
            ("Speed trend, 73.3K slack profiles, ", False),
            ("Fog limits (75/60/30 km/h), 60°C rail heat", True),
            (" & festival surges.", False),
        ]),
        ("4. Layer 2 — Arrival Window AI:", [
            ("3 Quantile GBDT models predict ", False),
            ("P10 / P50 / P90", True),
            (" (Transit R² = 0.987) + ", False),
            ("Delay-Jump Alert (0.92 AUC).", True),
        ]),
        ("5. Layer 3 — Physics & Manual Accident Ops:", [
            ("Space-Time DAG + ", False),
            ("Zero-Clash Platforms", True),
            (" + ", False),
            ("1-Click Manual Overrides", True),
            (" + ", False),
            ("25kV Detours.", True),
        ]),
        ("6. Feedback Self-Scoring Flywheel:", [
            ("SnapshotWriter + score_snapshots.py continuously audit predictions vs. actual arrivals to retrain AI.", False),
        ]),
    ]
    for idx, (title, runs) in enumerate(tech_cards):
        c = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(38), col_y + px(38 + idx * 47), px(510), px(44))
        c.fill.solid()
        c.fill.fore_color.rgb = C_GRAY_CARD
        c.line.color.rgb = C_BORDER_GRAY
        tf = c.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0.04)
        tf.margin_left = Inches(0.08)
        p = tf.paragraphs[0]
        r1 = p.add_run()
        r1.text = title + " "
        r1.font.name = FONT_SANS
        r1.font.bold = True
        r1.font.size = fpt(11.4)
        r1.font.color.rgb = C_NAVY_MED

        for r_txt, r_bold in runs:
            run = p.add_run()
            run.text = r_txt
            run.font.name = FONT_SANS
            run.font.bold = r_bold
            run.font.size = fpt(11)
            run.font.color.rgb = C_NAVY_TEXT

    # Trajectory Fan Chart Image
    tc_path = ASSETS_DIR / "traj_chart.png"
    if tc_path.exists():
        slide.shapes.add_picture(str(tc_path), px(38), col_y + px(332), width=px(510), height=px(214))

    # Right Panel (55% width) - Fresh Cropped DFD Diagram Image
    dfd_path = ASSETS_DIR / "dfd.png"
    if dfd_path.exists():
        slide.shapes.add_picture(str(dfd_path), px(568), col_y, width=px(684), height=col_h)

    # Bottom Process Ribbon with Individual Colored Pill Steps
    ribbon = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(28), px(634), px(1224), px(40))
    ribbon.fill.solid()
    ribbon.fill.fore_color.rgb = RGBColor(241, 245, 249)
    ribbon.line.color.rgb = RGBColor(148, 163, 184)

    # Label on left
    lbl_tx = slide.shapes.add_textbox(px(34), px(638), px(125), px(30))
    tf_l = lbl_tx.text_frame
    tf_l.margin_top = Inches(0.02)
    tf_l.margin_left = Inches(0)
    p = tf_l.paragraphs[0]
    p.text = "PROCESS FLOW:"
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(11.5)
    p.font.color.rgb = C_NAVY_DARK

    steps = [
        ("1. Multi-Source Scrape + Weather", C_NAVY_MED),
        ("2. 31-Feature G&SR Fusion", RGBColor(30, 64, 175)),
        ("3. Quantile GBDT (P10/50/90)", C_GREEN_DARK),
        ("4. Physics DAG + Manual Ops", C_PURPLE),
        ("5. FastAPI (<18ms)", C_BLUE_ACCENT),
        ("6. Self-Scoring DB Loop", C_TEAL),
    ]
    cur_x = 150
    pill_widths = [156, 150, 150, 150, 120, 135]
    for s_idx, (s_txt, s_col) in enumerate(steps):
        p_w = pill_widths[s_idx]
        step_pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(cur_x), px(639), px(p_w), px(30))
        step_pill.fill.solid()
        step_pill.fill.fore_color.rgb = s_col
        step_pill.line.fill.background()
        tf = step_pill.text_frame
        tf.margin_top = Inches(0.02)
        tf.margin_bottom = Inches(0)
        p = tf.paragraphs[0]
        p.text = s_txt
        p.alignment = PP_ALIGN.CENTER
        p.font.name = FONT_SANS
        p.font.bold = True
        p.font.size = fpt(9.6)
        p.font.color.rgb = C_WHITE

        cur_x += p_w + 4
        if s_idx < len(steps) - 1:
            arr_tx = slide.shapes.add_textbox(px(cur_x), px(638), px(18), px(30))
            tf_a = arr_tx.text_frame
            tf_a.margin_top = Inches(0.02)
            tf_a.margin_left = Inches(0)
            p = tf_a.paragraphs[0]
            p.text = "➔"
            p.alignment = PP_ALIGN.CENTER
            p.font.name = FONT_SANS
            p.font.bold = True
            p.font.size = fpt(11)
            p.font.color.rgb = RGBColor(100, 116, 139)
            cur_x += 20


# -------------------------------------------------------------
# SLIDE 4: Feasibility & Viability (1:1 Solutions)
# -------------------------------------------------------------
def build_slide4(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_common_decorations(
        slide,
        "FEASIBILITY AND VIABILITY",
        4,
        subtitle_text="❖ TECHNICAL FEASIBILITY, MINISTRY FINANCIAL ROI, REAL CHALLENGES & 1:1 SOLUTIONS",
        title_font_size=32
    )

    col_y = px(70)
    col_h = px(555)

    # Col 1: Feasibility & Economic Viability (width 31%)
    c1 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(28), col_y, px(375), col_h)
    c1.fill.solid()
    c1.fill.fore_color.rgb = C_GREEN_BG
    c1.line.color.rgb = RGBColor(187, 247, 208)

    hdr1 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(36), col_y + px(8), px(359), px(26))
    hdr1.fill.solid()
    hdr1.fill.fore_color.rgb = C_GREEN_DARK
    hdr1.line.fill.background()
    p = hdr1.text_frame.paragraphs[0]
    p.text = "1. FEASIBILITY & ECONOMIC VIABILITY"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(13)
    p.font.color.rgb = C_WHITE

    feas_cards = [
        ("✓ Self-Growing Public Data Lake (1.68 GB+)", [
            ("Built on ", False),
            ("1.51M real delays", True),
            (" & ", False),
            ("8,990 stations;", True),
            (" 24x7 scraper & feedback scorer grow the DB daily—", False),
            ("longer it runs, better it performs.", True),
        ]),
        ("✓ ₹0 Hardware Capex & <₹15K/mo Cloud Opex", [
            ("Saves ", False),
            ("₹120+ Cr in trackside/GPS hardware;", True),
            (" runs on standard CPU in ", False),
            ("<18ms", True),
            (" (zero GPU cost) with ", False),
            ("-79.9% scraper bandwidth.", True),
        ]),
        ("✓ High Railway Operational & Fuel ROI", [
            ("Prevents outer-signal train stops (saving ", False),
            ("150–200 kWh traction power / 35–50L diesel per stop", True),
            (") & cuts junction platform delays.", False),
        ]),
    ]
    for idx, (title, runs) in enumerate(feas_cards):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(36), col_y + px(48 + idx * 120), px(359), px(104))
        card.fill.solid()
        card.fill.fore_color.rgb = C_WHITE
        card.line.color.rgb = C_BORDER_GRAY
        tf = card.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0.08)
        tf.margin_left = Inches(0.08)
        p = tf.paragraphs[0]
        r1 = p.add_run()
        r1.text = title + "\n"
        r1.font.name = FONT_SANS
        r1.font.bold = True
        r1.font.size = fpt(11.8)
        r1.font.color.rgb = C_GREEN_DARK

        for r_txt, r_bold in runs:
            run = p.add_run()
            run.text = r_txt
            run.font.name = FONT_SANS
            run.font.bold = r_bold
            run.font.size = fpt(11.2)
            run.font.color.rgb = C_NAVY_TEXT

    # Clean Backtest Scorecard Image
    sc_path = ASSETS_DIR / "scorecard.png"
    if sc_path.exists():
        slide.shapes.add_picture(str(sc_path), px(36), col_y + px(408), width=px(359), height=px(124))

    # Col 2: Real Railway Challenges (width 31.5%)
    c2 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(415), col_y, px(375), col_h)
    c2.fill.solid()
    c2.fill.fore_color.rgb = C_RED_BG
    c2.line.color.rgb = RGBColor(254, 202, 202)

    hdr2 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(423), col_y + px(8), px(359), px(26))
    hdr2.fill.solid()
    hdr2.fill.fore_color.rgb = C_RED_DARK
    hdr2.line.fill.background()
    p = hdr2.text_frame.paragraphs[0]
    p.text = "2. REAL RAILWAY CHALLENGES"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(13)
    p.font.color.rgb = C_WHITE

    challenges = [
        ("⚠ Internal Railway GPS (RTIS/COA) is Closed", [
            ("ISRO 30s locomotive GPS and track signal relays are private CRIS systems unavailable to external teams.", False),
        ]),
        ("⚠ Extreme 12–24h Delays & No Early Departures", [
            ("Heavy delay outliers skew simple averages, while early trains must wait at stations until Scheduled Departure (", False),
            ("STD", True),
            (").", False),
        ]),
        ("⚠ Domino Congestion & Platform Clashes", [
            ("Standard AI predicts trains in isolation—putting two trains on Platform 1 at the exact same minute.", False),
        ]),
        ("⚠ Unpredicted Accidents & Renamed Stations", [
            ("Sudden derailments/accidents cannot be predicted from history alone; renamed stations (", False),
            ("ALD➔PRYJ", True),
            (") break data.", False),
        ]),
    ]
    for idx, (title, runs) in enumerate(challenges):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(423), col_y + px(42 + idx * 125), px(359), px(116))
        card.fill.solid()
        card.fill.fore_color.rgb = C_WHITE
        card.line.color.rgb = C_BORDER_GRAY
        tf = card.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0.06)
        tf.margin_left = Inches(0.08)
        p = tf.paragraphs[0]
        r1 = p.add_run()
        r1.text = title + "\n"
        r1.font.name = FONT_SANS
        r1.font.bold = True
        r1.font.size = fpt(11.6)
        r1.font.color.rgb = C_RED_DARK

        for r_txt, r_bold in runs:
            run = p.add_run()
            run.text = r_txt
            run.font.name = FONT_SANS
            run.font.bold = r_bold
            run.font.size = fpt(11)
            run.font.color.rgb = C_NAVY_TEXT

    # Connecting Arrows
    for idx in range(4):
        arrow = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(800), col_y + px(80 + idx * 125), px(44), px(28))
        arrow.fill.solid()
        arrow.fill.fore_color.rgb = C_BLUE_ACCENT
        arrow.line.fill.background()
        p = arrow.text_frame.paragraphs[0]
        p.text = "➔"
        p.alignment = PP_ALIGN.CENTER
        p.font.name = FONT_SANS
        p.font.bold = True
        p.font.size = Pt(14)
        p.font.color.rgb = C_WHITE

    # Col 3: 1:1 Solutions (width 31.5%)
    c3 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(855), col_y, px(395), col_h)
    c3.fill.solid()
    c3.fill.fore_color.rgb = C_BLUE_BG
    c3.line.color.rgb = RGBColor(191, 219, 254)

    hdr3 = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(865), col_y + px(8), px(375), px(26))
    hdr3.fill.solid()
    hdr3.fill.fore_color.rgb = C_BLUE_LINK
    hdr3.line.fill.background()
    p = hdr3.text_frame.paragraphs[0]
    p.text = "3. HOW DARPAN SOLVES THEM (1:1)"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(13)
    p.font.color.rgb = C_WHITE

    solutions = [
        ("🛡️ 4-Source Public Failover + 704 Cabin Queue Math", [
            ("Cascades across ", False),
            ("ConfirmTkt/NTES/eRail", True),
            (" + predicts outer-signal wait times across ", False),
            ("704 mapped Approach Cabins.", True),
        ]),
        ("🛡️ P10/P50/P90 Window AI + Schedule Clamp", [
            ("Asymmetric quantile AI clamped at ", False),
            ("STD", True),
            (" cuts typical error from ", False),
            ("4.93m to 1.49m (-70%)", True),
            (" with ", False),
            ("85.3% window coverage.", True),
        ]),
        ("🛡️ Zero-Clash Platform Assigner + Overtaking Rules", [
            ("IntervalTree", True),
            (" enforces 5-min platform gaps, ", False),
            ("COA 6-Tier priority overtaking", True),
            (", & following-train headway cascades.", False),
        ]),
        ("🛡️ Manual Accident Input + 25kV Detour + Code Bridge", [
            ("1-Click Operator Accident Input (", False),
            ("POST /v1/deta/incidents", True),
            (") triggers ", False),
            ("25kV detours", True),
            (" in <5ms; rescues ", False),
            ("72.5K alias rows.", True),
        ]),
    ]
    for idx, (title, runs) in enumerate(solutions):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(865), col_y + px(42 + idx * 125), px(375), px(116))
        card.fill.solid()
        card.fill.fore_color.rgb = C_WHITE
        card.line.color.rgb = C_BORDER_GRAY
        tf = card.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0.06)
        tf.margin_left = Inches(0.08)
        p = tf.paragraphs[0]
        r1 = p.add_run()
        r1.text = title + "\n"
        r1.font.name = FONT_SANS
        r1.font.bold = True
        r1.font.size = fpt(11.6)
        r1.font.color.rgb = C_BLUE_LINK

        for r_txt, r_bold in runs:
            run = p.add_run()
            run.text = r_txt
            run.font.name = FONT_SANS
            run.font.bold = r_bold
            run.font.size = fpt(11)
            run.font.color.rgb = C_NAVY_TEXT

    # Bottom Link Bar with Clickable Hyperlinks
    link_bar = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(28), px(634), px(1224), px(36))
    link_bar.fill.solid()
    link_bar.fill.fore_color.rgb = C_BLUE_BG
    link_bar.line.color.rgb = RGBColor(147, 197, 253)
    tf = link_bar.text_frame
    tf.margin_top = Inches(0.04)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER

    r1 = p.add_run()
    r1.text = "❖ Live Portal: "
    r1.font.name = FONT_SANS
    r1.font.bold = True
    r1.font.size = fpt(12)
    r1.font.color.rgb = C_NAVY_TEXT

    r2 = p.add_run()
    r2.text = "https://team-twarit-sih26028.vercel.app"
    r2.font.name = FONT_SANS
    r2.font.bold = True
    r2.font.size = fpt(12)
    r2.font.color.rgb = C_BLUE_LINK
    r2.font.underline = True
    r2.hyperlink.address = "https://team-twarit-sih26028.vercel.app"

    r3 = p.add_run()
    r3.text = "   ❖ Demo Video: "
    r3.font.name = FONT_SANS
    r3.font.bold = True
    r3.font.size = fpt(12)
    r3.font.color.rgb = C_NAVY_TEXT

    r4 = p.add_run()
    r4.text = "Google Drive Demo Link"
    r4.font.name = FONT_SANS
    r4.font.bold = True
    r4.font.size = fpt(12)
    r4.font.color.rgb = C_BLUE_LINK
    r4.font.underline = True
    r4.hyperlink.address = "https://drive.google.com/file/d/1Qz0DTqZIDW14FyF7VVWAgwwtTXFZS6QE"

    r5 = p.add_run()
    r5.text = "   🔗 [Click on blue texts to open link]"
    r5.font.name = FONT_SANS
    r5.font.bold = True
    r5.font.size = fpt(11.5)
    r5.font.color.rgb = RGBColor(71, 85, 105)


# -------------------------------------------------------------
# SLIDE 5: Impact & Benefits + Native PowerPoint Table
# -------------------------------------------------------------
def build_slide5(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_common_decorations(slide, "IMPACT AND BENEFITS", 5)

    # 4 Stakeholder Cards (Top Row)
    card_w = px(292)
    card_h = px(175)
    st_cards = [
        ("1. PASSENGERS (APP & PNR)", [
            ("❖ Shows ", False),
            ("Best (P10), Expected (P50), & Worst-Case (P90)", True),
            (" arrival times instead of a single guess.\n❖ Displays exact ", False),
            ("buffer time recovered (-14m)", True),
            (", fog speed alerts, & privacy-safe 10-digit PNR tracking.", False),
        ], "85.3% Window Accuracy"),
        ("2. STATION MASTERS (PLATFORMS)", [
            ("❖ ", False),
            ("Zero-Clash Platform Assigner", True),
            (" enforces 5-min safety gaps & warns of ", False),
            ("OUTER HOLD +12m", True),
            (" delays early.\n❖ Predicts ", False),
            ("Festival Crowd Dwell Surges", True),
            (" (Maha Kumbh 3.2x) for cleaning, crew & cab/bus planning.", False),
        ], "704 Approach Cabins Mapped"),
        ("3. CONTROL ROOMS (MANUAL OPS)", [
            ("❖ ", False),
            ("Manual Accident Override Input:", True),
            (" Operators inject unpredicted accidents (Derailment, Cattle Hit, Wire Snap).\n❖ Instantly recomputes downstream domino ETAs & ", False),
            ("25kV Electrified Detour Routes", True),
            (" (Yen's K-Path).", False),
        ], "Manual Accident + 25kV Detour"),
        ("4. SELF-LEARNING RAILWAY API", [
            ("❖ Fast ", False),
            ("/v1/deta/*", True),
            (" REST APIs + ", False),
            ("24x7 Self-Growing DB", True),
            (" that scrapes runs & learns from prediction feedback.\n❖ Tags every value with honest source (live/cache/schedule) at ", False),
            ("<1.5ms cached latency", True),
            (" across 17 zones.", False),
        ], "MedAE: 1.49m (-70% Error)"),
    ]
    for idx, (title, runs, pill) in enumerate(st_cards):
        c = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(28 + idx * 308), px(68), card_w, card_h)
        c.fill.solid()
        c.fill.fore_color.rgb = C_WHITE
        c.line.color.rgb = C_BORDER_GRAY
        tf = c.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0.06)
        tf.margin_left = Inches(0.08)

        p = tf.paragraphs[0]
        p.text = title
        p.font.name = FONT_SANS
        p.font.bold = True
        p.font.size = fpt(12.5)
        p.font.color.rgb = C_NAVY_MED
        p.space_after = Pt(4)

        p2 = tf.add_paragraph()
        for r_txt, r_bold in runs:
            run = p2.add_run()
            run.text = r_txt
            run.font.name = FONT_SANS
            run.font.bold = r_bold
            run.font.size = fpt(11.2)
            run.font.color.rgb = C_NAVY_TEXT
        p2.space_after = Pt(4)

        # Bottom Pill Shape
        bpill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(38 + idx * 308), px(215), px(272), px(22))
        bpill.fill.solid()
        bpill.fill.fore_color.rgb = C_BLUE_BG
        bpill.line.color.rgb = RGBColor(191, 219, 254)
        tf_bp = bpill.text_frame
        tf_bp.margin_top = Inches(0)
        tf_bp.margin_bottom = Inches(0)
        p = tf_bp.paragraphs[0]
        p.text = pill
        p.alignment = PP_ALIGN.CENTER
        p.font.name = FONT_MONO
        p.font.bold = True
        p.font.size = fpt(10.5)
        p.font.color.rgb = C_BLUE_LINK

    # 3-Pillar Macro Impact Strip (Middle)
    macro_y = px(248)
    macro_w = px(395)
    macro_h = px(66)

    macros = [
        ("👥 SOCIAL IMPACT (2.4 Cr Daily Passengers)", "Eliminates platform waiting anxiety & missed train connections; improves station crowd safety during festivals.", C_BLUE_BG, RGBColor(147, 197, 253), C_NAVY_MED),
        ("💰 ECONOMIC IMPACT (₹120+ Cr Capex Saved)", "Boosts throughput on >100% congested trunk lines with zero new hardware; cuts crew overtime & rake detention.", C_GREEN_BG, RGBColor(134, 239, 172), C_GREEN_DARK),
        ("🌱 ENVIRONMENTAL & ENERGY IMPACT", "Prevents unscheduled outer-signal stops of 24-coach rakes, saving 150–200 kWh power / 35–50L diesel per stop.", C_AMBER_BG, RGBColor(253, 230, 138), C_AMBER),
    ]
    for idx, (title, desc, bg, border, tc) in enumerate(macros):
        b = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(28 + idx * 414), macro_y, macro_w, macro_h)
        b.fill.solid()
        b.fill.fore_color.rgb = bg
        b.line.color.rgb = border
        tf = b.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0.04)
        tf.margin_left = Inches(0.08)
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = FONT_SANS
        p.font.bold = True
        p.font.size = fpt(11.8)
        p.font.color.rgb = tc
        p.space_after = Pt(2)
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.name = FONT_SANS
        p2.font.size = fpt(10.8)
        p2.font.color.rgb = C_NAVY_TEXT

    # Table Header Strip above Table
    th_bar = slide.shapes.add_textbox(px(28), px(318), px(800), px(24))
    tf_th = th_bar.text_frame
    tf_th.margin_top = Inches(0)
    tf_th.margin_left = Inches(0)
    p = tf_th.paragraphs[0]
    p.text = "How DARPAN Beats Existing Railway Formulas, Consumer Apps & Academic Models"
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(11.8)
    p.font.color.rgb = C_NAVY_TEXT

    th_pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(880), px(318), px(372), px(20))
    th_pill.fill.solid()
    th_pill.fill.fore_color.rgb = C_GREEN_BG
    th_pill.line.color.rgb = RGBColor(187, 247, 208)
    tf_tp = th_pill.text_frame
    tf_tp.margin_top = Inches(0)
    tf_tp.margin_bottom = Inches(0)
    p = tf_tp.paragraphs[0]
    p.text = "Self-Growing DB + Manual Accident Override Included"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_MONO
    p.font.bold = True
    p.font.size = fpt(9.8)
    p.font.color.rgb = C_GREEN_DARK

    # Benchmark Table (REAL NATIVE POWERPOINT TABLE)
    tbl_y = px(342)
    table_shape = slide.shapes.add_table(6, 7, px(28), tbl_y, px(1224), px(330))
    tbl = table_shape.table

    col_widths = [px(240), px(160), px(170), px(170), px(170), px(160), px(154)]
    for j, w in enumerate(col_widths):
        tbl.columns[j].width = w

    headers = [
        "System / Baseline",
        "Arrival Window (P10/P50/P90)",
        "Fog & Track-Heat Speed Rules",
        "Overtaking & Domino Delay",
        "Zero-Clash Platform & Outer Hold",
        "Self-Growing DB & Manual Accident Ops",
        "Typical Error (MedAE) & Score",
    ]
    for j, h in enumerate(headers):
        cell = tbl.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = C_NAVY_DARK
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.alignment = PP_ALIGN.CENTER
        p.font.name = FONT_SANS
        p.font.bold = True
        p.font.size = fpt(11)
        p.font.color.rgb = C_WHITE

    rows_data = [
        ("Old Railway Formula (STA + Delay − Buffer)", "✕ Single Time", "✕ None", "✕ Isolated", "✕ None", "✕ Static Table", "4.93m (1/6) 🔴"),
        ("Consumer Apps (Where Is My Train / NTES)", "~ Single Time", "✕ None", "✕ Isolated", "✕ Unaware", "✕ Read-Only App", "Linear (1.5/6) 🟠"),
        ("Academic GNN (IIT-KGP RSTGCN, 2024)", "✕ Hourly Stn Avg", "✕ No Weather", "~ Station Graph", "✕ No Platforms", "✕ Frozen CSV", "Stn Avg (2/6) 🟠"),
        ("Other SIH Repos (Simulated / Basic ML)", "~ Synthetic CI", "✕ Month Lookup", "✕ No Overtaking", "✕ Platform Clashes", "✕ No Feedback DB", "Synthetic (2.5/6) 🟠"),
        ("DARPAN (Team Twarit — SIH26028) 🏆 BEST 6/6", "✓ P10 / P50 / P90", "✓ 3.19M Wx + G&SR", "✓ COA + FIFO Graph", "✓ 704 Cabins + Tree", "✓ Auto-Scrape + Ops", "1.49m (6/6) 🟢 🏆"),
    ]
    for i, r_vals in enumerate(rows_data):
        is_darpan = (i == 4)
        for j, val in enumerate(r_vals):
            cell = tbl.cell(i + 1, j)
            cell.fill.solid()
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            if is_darpan:
                cell.fill.fore_color.rgb = RGBColor(254, 249, 195) # Gold cream highlight
            else:
                cell.fill.fore_color.rgb = C_WHITE if (i % 2 == 0) else RGBColor(248, 250, 252)
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.alignment = PP_ALIGN.CENTER if j > 0 else PP_ALIGN.LEFT
            p.font.name = FONT_SANS
            p.font.bold = is_darpan or (j == 0)
            p.font.size = fpt(11)
            if is_darpan:
                p.font.color.rgb = C_GREEN_DARK if (j == 6 or "✓" in val) else C_NAVY_TEXT
            elif val.startswith("✓"):
                p.font.color.rgb = C_GREEN_DARK
            elif val.startswith("✕"):
                p.font.color.rgb = C_RED_DARK
            elif val.startswith("~"):
                p.font.color.rgb = C_AMBER
            else:
                p.font.color.rgb = C_NAVY_TEXT


# -------------------------------------------------------------
# SLIDE 6: Research, References, Visual Analytics & QR
# -------------------------------------------------------------
def build_slide6(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_common_decorations(slide, "RESEARCH AND REFERENCES", 6)

    col_y = px(70)
    col_h = px(560)

    # Left Panel (width: 49%)
    lp_w = px(600)
    lp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(28), col_y, lp_w, col_h)
    lp.fill.solid()
    lp.fill.fore_color.rgb = C_WHITE
    lp.line.color.rgb = C_BORDER_GRAY
    lp.line.width = Pt(1.5)

    l_hdr = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(38), col_y + px(8), px(580), px(26))
    l_hdr.fill.solid()
    l_hdr.fill.fore_color.rgb = C_NAVY_DARK
    l_hdr.line.fill.background()
    p = l_hdr.text_frame.paragraphs[0]
    p.text = "VERIFIED RAILWAY AUDITS, PAPERS & CLICKABLE SOURCES"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(13)
    p.font.color.rgb = C_WHITE

    ref_cards = [
        ("1. Indian Railways CAG Audit & Official Operating Rules (G&SR)", "Govt Audits", [
            ("• CAG Report No. 22 of 2021 (Para 2.1): ", True, C_BLUE_LINK),
            ("Proves fixed Engineering & Traffic Recovery buffers fail on ", False, C_NAVY_TEXT),
            (">100% congested High-Density Network (HDN)", True, C_NAVY_TEXT),
            (" corridors.\n", False, C_NAVY_TEXT),
            ("• Indian Railways G&SR Rule 3.61 & Track Manual Para 5.2: ", True, C_BLUE_LINK),
            ("Official Fog-Pass GPS speed caps (", False, C_NAVY_TEXT),
            ("75 km/h with FPD vs 60 km/h standard", True, C_NAVY_TEXT),
            (") & ", False, C_NAVY_TEXT),
            ("60°C track-heat", True, C_NAVY_TEXT),
            (" limits.\n", False, C_NAVY_TEXT),
            ("Sources: cag.gov.in · indianrailways.gov.in · cris.org.in", False, RGBColor(100, 116, 139)),
        ]),
        ("2. Machine Learning, Arrival Window Calibration & Graph Routing", "Peer-Reviewed", [
            ("• IIT Kharagpur Railway Graph Study (Chowdhury et al., IEEE T-ITS 2024): ", True, C_BLUE_LINK),
            ("'RSTGCN: Spatio-Temporal Graph Convolutional Network' across 4,735 Indian stations.\n", False, C_NAVY_TEXT),
            ("• LightGBM Quantile GBDT (NeurIPS 2017) & Conformal Quantile Regression (NeurIPS 2019): ", True, C_BLUE_LINK),
            ("Calibrated P10/P50/P90 windows + ", False, C_NAVY_TEXT),
            ("Yen's 25kV Detours (1971)", True, C_NAVY_TEXT),
            (".\n", False, C_NAVY_TEXT),
            ("Sources: arxiv.org/abs/2510.01262 · arxiv.org/abs/1905.03222", False, RGBColor(100, 116, 139)),
        ]),
        ("3. Self-Growing 6-DB Data Lake (1.68 GB) & Open Datasets", "Live & Growing", [
            ("• DataMeet Indian Railways Topology + stations.db: ", True, C_BLUE_LINK),
            ("8,990 stations, 420K halts, 704 cabins + Renamed-Station Code Translator (", False, C_NAVY_TEXT),
            ("72,508 records recovered", True, C_NAVY_TEXT),
            (").\n", False, C_NAVY_TEXT),
            ("• historical.db (1.51M delays, 73,342 slack profiles) + Open-Meteo Weather Grid (3.19M rows) + 24x7 SnapshotWriter feedback loop.\n", False, C_NAVY_TEXT),
            ("Sources: github.com/datameet/railways · open-meteo.com", False, RGBColor(100, 116, 139)),
        ]),
    ]
    for idx, (title, badge_txt, runs) in enumerate(ref_cards):
        c = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(38), col_y + px(38 + idx * 116), px(580), px(110))
        c.fill.solid()
        c.fill.fore_color.rgb = C_GRAY_CARD
        c.line.color.rgb = C_BORDER_GRAY
        tf = c.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0.04)
        tf.margin_left = Inches(0.08)
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = FONT_SANS
        p.font.bold = True
        p.font.size = fpt(11.8)
        p.font.color.rgb = C_BLUE_LINK
        p.space_after = Pt(2)

        p2 = tf.add_paragraph()
        for r_txt, r_bold, r_col in runs:
            run = p2.add_run()
            run.text = r_txt
            run.font.name = FONT_SANS
            run.font.bold = r_bold
            run.font.size = fpt(10.8)
            run.font.color.rgb = r_col

        # Pill badge top right of card
        bdg = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(520), col_y + px(42 + idx * 116), px(90), px(18))
        bdg.fill.solid()
        bdg.fill.fore_color.rgb = C_BLUE_BG if idx < 2 else C_GREEN_BG
        bdg.line.color.rgb = RGBColor(191, 219, 254) if idx < 2 else RGBColor(187, 247, 208)
        tf_b = bdg.text_frame
        tf_b.margin_top = Inches(0)
        tf_b.margin_bottom = Inches(0)
        p = tf_b.paragraphs[0]
        p.text = badge_txt
        p.alignment = PP_ALIGN.CENTER
        p.font.name = FONT_MONO
        p.font.bold = True
        p.font.size = fpt(8.8)
        p.font.color.rgb = C_BLUE_LINK if idx < 2 else C_GREEN_DARK

    # QR Code Card (Bottom of Left Panel)
    qr_card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(38), col_y + px(392), px(580), px(155))
    qr_card.fill.solid()
    qr_card.fill.fore_color.rgb = C_BLUE_BG
    qr_card.line.color.rgb = C_BLUE_ACCENT
    qr_card.line.width = Pt(1.5)

    qr_path = ASSETS_DIR / "qr.png"
    if qr_path.exists():
        slide.shapes.add_picture(str(qr_path), px(48), col_y + px(405), width=px(125), height=px(125))

    qr_tx = slide.shapes.add_textbox(px(185), col_y + px(405), px(420), px(130))
    tf = qr_tx.text_frame
    tf.word_wrap = True
    tf.margin_top = Inches(0.04)
    tf.margin_left = Inches(0.08)
    p = tf.paragraphs[0]
    p.text = "📱 SCAN QR OR CLICK LINKS TO TEST LIVE PROTOTYPE"
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(13)
    p.font.color.rgb = C_NAVY_MED
    p.space_after = Pt(4)

    p2 = tf.add_paragraph()
    r1 = p2.add_run()
    r1.text = "• Live Web Portal: "
    r1.font.name = FONT_SANS
    r1.font.bold = True
    r1.font.size = fpt(11.2)
    r1.font.color.rgb = C_NAVY_TEXT

    r2 = p2.add_run()
    r2.text = "https://team-twarit-sih26028.vercel.app\n"
    r2.font.name = FONT_SANS
    r2.font.bold = True
    r2.font.size = fpt(11.2)
    r2.font.color.rgb = C_BLUE_LINK
    r2.font.underline = True
    r2.hyperlink.address = "https://team-twarit-sih26028.vercel.app"

    r3 = p2.add_run()
    r3.text = "• Demo Video: "
    r3.font.name = FONT_SANS
    r3.font.bold = True
    r3.font.size = fpt(11.2)
    r3.font.color.rgb = C_NAVY_TEXT

    r4 = p2.add_run()
    r4.text = "Google Drive Walkthrough\n"
    r4.font.name = FONT_SANS
    r4.font.bold = True
    r4.font.size = fpt(11.2)
    r4.font.color.rgb = C_BLUE_LINK
    r4.font.underline = True
    r4.hyperlink.address = "https://drive.google.com/file/d/1Qz0DTqZIDW14FyF7VVWAgwwtTXFZS6QE"

    r5 = p2.add_run()
    r5.text = "• Instant API & Interactive Platform Maps across 17 Zones."
    r5.font.name = FONT_SANS
    r5.font.size = fpt(11.2)
    r5.font.color.rgb = C_NAVY_TEXT

    # Right Panel (width: 49%) - Visual Analytics
    rp_w = px(610)
    rp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(642), col_y, rp_w, col_h)
    rp.fill.solid()
    rp.fill.fore_color.rgb = C_WHITE
    rp.line.color.rgb = C_BORDER_GRAY
    rp.line.width = Pt(1.5)

    r_hdr = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(652), col_y + px(8), px(590), px(26))
    r_hdr.fill.solid()
    r_hdr.fill.fore_color.rgb = C_NAVY_DARK
    r_hdr.line.fill.background()
    p = r_hdr.text_frame.paragraphs[0]
    p.text = "VISUAL ANALYTICS: SELF-GROWING DB FLYWHEEL & DELAY DRIVERS"
    p.alignment = PP_ALIGN.CENTER
    p.font.name = FONT_SANS
    p.font.bold = True
    p.font.size = fpt(13)
    p.font.color.rgb = C_WHITE

    # Graph 1 (Flywheel Curve) Image
    fw_path = ASSETS_DIR / "flywheel.png"
    if fw_path.exists():
        slide.shapes.add_picture(str(fw_path), px(652), col_y + px(40), width=px(590), height=px(235))

    # Graph 2 (Delay Driver Features) Image
    ft_path = ASSETS_DIR / "features.png"
    if ft_path.exists():
        slide.shapes.add_picture(str(ft_path), px(652), col_y + px(282), width=px(590), height=px(265))

    # Bottom Link Bar
    link_bar = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, px(28), px(636), px(1224), px(36))
    link_bar.fill.solid()
    link_bar.fill.fore_color.rgb = C_BLUE_BG
    link_bar.line.color.rgb = RGBColor(147, 197, 253)
    tf = link_bar.text_frame
    tf.margin_top = Inches(0.04)
    p = tf.paragraphs[0]
    r1 = p.add_run()
    r1.text = "🔗 [Click on blue texts to open link] — Every research study (IIT Kharagpur RSTGCN, NeurIPS), CAG Audit & Live Demo URL above is directly clickable                    "
    r1.font.name = FONT_SANS
    r1.font.bold = True
    r1.font.size = fpt(11.8)
    r1.font.color.rgb = C_NAVY_MED

    r2 = p.add_run()
    r2.text = "Open Live Portal ↗"
    r2.font.name = FONT_SANS
    r2.font.bold = True
    r2.font.size = fpt(11.8)
    r2.font.color.rgb = C_BLUE_LINK
    r2.font.underline = True
    r2.hyperlink.address = "https://team-twarit-sih26028.vercel.app"


SPEAKER_NOTES = [
    (
        "Slide 1: Title & Team Deliverables\n"
        "• Problem Statement ID: SIH26028\n"
        "• Title: Dynamic Forecast of Expected Time of Arrival (ETA) for Coaching Trains\n"
        "• Organization: Ministry of Railways (MIC)\n"
        "• Team: Twarit (ID: 131076)\n"
        "• Highlights: 1.68 GB 6-DB Rail Data Lake, 8,990 stations, 704 cabins, 70% median error cut (4.93m -> 1.49m)."
    ),
    (
        "Slide 2: Core Idea & Solution Mindmap\n"
        "• Replaces static schedule + delay - buffer with a 2-Pass Hybrid Engine (Quantile GBDT AI + Space-Time DAG physics).\n"
        "• Includes Mindmap showing 6 radial capabilities: P10/P50/P90 quantile drift, 704 cabins outer hold, COA 6-tier overtaking, G&SR fog/heat rules, self-growing feedback DB, and 1-click manual accident overrides with 25kV detours."
    ),
    (
        "Slide 3: Technical Approach & Data Flow Diagram (DFD)\n"
        "• Left: 6-layer technology stack and live 12301 Howrah-New Delhi Rajdhani trajectory fan chart.\n"
        "• Right: Level 1/2 Data Flow Diagram (DFD) with 4 external stakeholder entities, cloud feeds, 1.68 GB database cylinder, 3 decision diamonds (Delay > 5m?, Platform Clash?, Accident/Block?), and continuous feedback flywheel.\n"
        "• Bottom: 6-stage linear process flow ribbon."
    ),
    (
        "Slide 4: Feasibility & Economic Viability\n"
        "• Technical Feasibility: Built entirely on 1.68 GB public rail data; runs in <18ms on standard CPU.\n"
        "• Financial ROI: Zero locomotive GPS/trackside hardware capex (saving Indian Railways ₹120+ Crores); < ₹15,000/month cloud opex.\n"
        "• Operational/Fuel ROI: Prevents unscheduled outer-signal stops of 24-coach rakes (saving 150-200 kWh traction power / 35-50L diesel per stop).\n"
        "• 4 Real Railway Challenges paired 1:1 with engineering solutions."
    ),
    (
        "Slide 5: Impact and Benefits\n"
        "• 4 Stakeholder views: Passengers (P10/P50/P90 ETA & PNR), Station Masters (Zero-Clash 5m buffer), Controllers (Dispatch cockpit), and Self-Learning API.\n"
        "• 3-Pillar Macro Impact: Social (2.4 Cr daily passengers), Economic (₹120+ Cr saved), Environmental (outer-signal stop energy cut).\n"
        "• Competitor Benchmark Table: DARPAN beats existing formulas, consumer apps, and academic GNNs 6/6."
    ),
    (
        "Slide 6: Research, Clickable References & Visual Analytics\n"
        "• Verified academic & government citations (IIT Kharagpur RSTGCN 2024, CAG Report 22 of 2021, Indian Railways G&SR, LightGBM/CQR).\n"
        "• Scannable QR code linking to live working web portal (https://team-twarit-sih26028.vercel.app).\n"
        "• Visual Graph 1: Self-Growing DB Flywheel curve showing error decaying 4.93m -> 1.49m as DB grows to 3.0M+ rows.\n"
        "• Visual Graph 2: Top learned delay drivers feature importance chart + 1.68 GB 6-DB storage distribution bar."
    ),
]


def main():
    prs = Presentation()
    # 16:9 Widescreen dimensions: 13.333 x 7.5 inches
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    print("Building Slide 1...")
    build_slide1(prs)
    print("Building Slide 2...")
    build_slide2(prs)
    print("Building Slide 3...")
    build_slide3(prs)
    print("Building Slide 4...")
    build_slide4(prs)
    print("Building Slide 5...")
    build_slide5(prs)
    print("Building Slide 6...")
    build_slide6(prs)

    # Attach speaker notes to all 6 slides
    for i, notes_txt in enumerate(SPEAKER_NOTES):
        notes_slide = prs.slides[i].notes_slide
        tf = notes_slide.notes_text_frame
        tf.text = notes_txt

    prs.save(str(OUT_PPTX))
    print(f"SUCCESS: Saved fully editable PPTX presentation to {OUT_PPTX}")
    print(f"File size: {OUT_PPTX.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
