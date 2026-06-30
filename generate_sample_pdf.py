"""
Generate a synthetic resume PDF for demo/testing.
Uses fpdf2 to create a realistic one-page resume.

Run:
    python generate_sample_pdf.py
    → creates sample_inputs/resume.pdf
"""

import os


def generate_resume_pdf(output_path: str = "sample_inputs/resume.pdf") -> None:
    try:
        from fpdf import FPDF
    except ImportError:
        print("fpdf2 not installed. Run: pip install fpdf2")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # ── Header ────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 12, "Priyanshu Choudhary", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 7, "Backend Engineer | Open Source Contributor", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Bangalore, India", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 6,
             "priyanshu@gmail.com  |  +91 9876543210  |  github.com/priyanshu-dev  |  linkedin.com/in/priyanshu-dev",
             new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.ln(4)
    pdf.set_draw_color(100, 100, 100)
    pdf.set_line_width(0.5)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(4)

    def section_header(title: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(0, 8, f"  {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(2)

    def body(text: str) -> None:
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(0, 6, text)
        pdf.ln(1)

    def bullet(text: str) -> None:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_x(25)  # slight indent
        pdf.multi_cell(0, 6, f"- {text}", new_x="LMARGIN", new_y="NEXT")

    # ── Skills ────────────────────────────────────────────────────────────────
    section_header("SKILLS")
    body("C++, NodeJS, MongoDB, ExpressJS, Docker, Kubernetes, Python, REST API, System Design, Git, Linux")

    # ── Experience ────────────────────────────────────────────────────────────
    section_header("EXPERIENCE")

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "Backend Engineer - TechCorp Solutions", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 5, "Jan 2022 - Present", new_x="LMARGIN", new_y="NEXT")
    bullet("Designed and deployed microservices handling 1M+ daily requests")
    bullet("Reduced API latency by 40% through caching with Redis and query optimization")
    bullet("Led migration of monolith to event-driven architecture using Kafka")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "Software Developer Intern - StartupXYZ", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 5, "Jun 2021 - Dec 2021", new_x="LMARGIN", new_y="NEXT")
    bullet("Built RESTful APIs for a SaaS product serving 500+ users")
    bullet("Implemented JWT-based authentication and role-based access control")
    pdf.ln(3)

    # ── Education ─────────────────────────────────────────────────────────────
    section_header("EDUCATION")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "B.Tech Computer Science & Engineering - NIT Raipur", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 5, "2018 - 2022  |  CGPA: 8.7 / 10", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ── Projects ──────────────────────────────────────────────────────────────
    section_header("PROJECTS")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "Distributed Cache (github.com/priyanshu-dev/distributed-cache)", new_x="LMARGIN", new_y="NEXT")
    bullet("Built a distributed in-memory cache in Go supporting LRU eviction")
    bullet("Achieved sub-millisecond read latency with consistent hashing")
    pdf.ln(2)

    # ── Footer ────────────────────────────────────────────────────────────────
    pdf.set_y(-15)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, "Generated for demo purposes", align="C")

    pdf.output(output_path)
    print(f"✓ Resume PDF generated: {output_path}")


if __name__ == "__main__":
    generate_resume_pdf()
