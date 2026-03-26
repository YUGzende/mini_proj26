#!/usr/bin/env python3
"""
analyze.py — Resume ATS Analysis Engine
========================================
This script:
1. Extracts text from a PDF resume using pdfplumber
2. Analyzes the resume against a selected job role (or custom description)
3. Scores it on 4 criteria:
   - Keyword matching (50%)
   - Section detection (20%)
   - Action words (20%)
   - Resume length (10%)
4. Returns a JSON result to stdout (read by Node.js backend)

Usage:
    python3 analyze.py <pdf_path> <job_role> [custom_description]
"""

import sys
import json
import re
import pdfplumber


# ═══════════════════════════════════════════════════════════════
# SKILL SETS PER JOB ROLE
# Each role has a list of relevant technical skills / keywords.
# These are matched against the resume text.
# ═══════════════════════════════════════════════════════════════
JOB_ROLES = {
    "software developer": [
        "python", "java", "c++", "c#", "algorithms", "data structures",
        "git", "github", "object oriented", "oop", "rest api", "api",
        "unit testing", "agile", "scrum", "linux", "sql", "docker",
        "problem solving", "debugging", "software development"
    ],
    "data analyst": [
        "python", "sql", "excel", "power bi", "tableau", "statistics",
        "data visualization", "data cleaning", "pandas", "numpy",
        "r", "google analytics", "etl", "reporting", "dashboards",
        "hypothesis testing", "regression", "data analysis", "mysql", "postgresql"
    ],
    "web developer": [
        "html", "css", "javascript", "react", "node", "nodejs",
        "typescript", "angular", "vue", "express", "rest api",
        "responsive design", "git", "npm", "webpack", "tailwind",
        "bootstrap", "mongodb", "sql", "deployment", "frontend", "backend"
    ],
    "ai/ml engineer": [
        "python", "machine learning", "deep learning", "tensorflow",
        "pytorch", "keras", "scikit-learn", "pandas", "numpy",
        "nlp", "computer vision", "neural networks", "data preprocessing",
        "model evaluation", "feature engineering", "statistics",
        "linear algebra", "transformers", "llm", "openai"
    ]
}

# ═══════════════════════════════════════════════════════════════
# ACTION WORDS — Strong resume verbs that signal achievement
# ═══════════════════════════════════════════════════════════════
ACTION_WORDS = [
    "developed", "built", "created", "designed", "implemented",
    "architected", "deployed", "optimized", "improved", "reduced",
    "increased", "led", "managed", "collaborated", "delivered",
    "automated", "integrated", "analyzed", "researched", "launched",
    "engineered", "solved", "achieved", "maintained", "mentored",
    "spearheaded", "streamlined", "established", "enhanced"
]

# ═══════════════════════════════════════════════════════════════
# SECTION KEYWORDS — Detects key resume sections
# ═══════════════════════════════════════════════════════════════
SECTION_KEYWORDS = {
    "education":   ["education", "degree", "university", "college", "b.tech", "b.sc", "bachelor", "master", "phd"],
    "skills":      ["skills", "technical skills", "core competencies", "technologies", "tools"],
    "projects":    ["projects", "personal projects", "academic projects", "work samples", "portfolio"],
    "experience":  ["experience", "work experience", "internship", "employment", "professional experience"]
}

# ═══════════════════════════════════════════════════════════════
# RECOMMENDATIONS PER ROLE
# Specific, actionable advice when certain skills are missing
# ═══════════════════════════════════════════════════════════════
ROLE_RECOMMENDATIONS = {
    "software developer": [
        "Add more algorithmic problem-solving experience (LeetCode, HackerRank).",
        "Mention version control tools — Git and GitHub are essential.",
        "Include any open-source contributions or personal GitHub projects.",
        "Highlight OOP concepts and software design patterns you've used.",
        "Add testing experience — unit tests, integration tests."
    ],
    "data analyst": [
        "Showcase SQL query examples or data projects in your portfolio.",
        "Add Power BI or Tableau dashboards if you have them.",
        "Mention statistical analysis methods you've applied.",
        "Include Python libraries: Pandas, NumPy, Matplotlib.",
        "Quantify your impact — 'reduced report generation time by 30%' stands out."
    ],
    "web developer": [
        "List specific frontend frameworks: React, Angular, or Vue.js.",
        "Include a portfolio link or GitHub with live projects.",
        "Mention responsive design and cross-browser compatibility experience.",
        "Add backend skills: Node.js, Express, or any REST API work.",
        "Deployment experience (Netlify, Vercel, AWS) adds great value."
    ],
    "ai/ml engineer": [
        "Include specific ML projects with models, datasets, and results.",
        "List deep learning frameworks: TensorFlow, PyTorch, or Keras.",
        "Add Kaggle competitions or research papers if applicable.",
        "Mention data preprocessing and feature engineering pipelines.",
        "Quantify model performance: accuracy, F1-score, etc."
    ]
}


# ───────────────────────────────────────────────────────────────
# STEP 1: Extract text from PDF using pdfplumber
# ───────────────────────────────────────────────────────────────
def extract_text_from_pdf(pdf_path):
    """Reads all pages of a PDF and returns combined plain text."""
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


# ───────────────────────────────────────────────────────────────
# STEP 2: Extract keywords from a custom job description
# Simple NLP: removes stopwords, extracts meaningful words
# ───────────────────────────────────────────────────────────────
def extract_keywords_from_description(description):
    """
    Extracts meaningful keywords from a custom job description.
    Removes common English stopwords to focus on skill/tech terms.
    """
    # Common stopwords to ignore
    stopwords = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "is", "are", "was", "were", "be", "been",
        "have", "has", "will", "would", "should", "can", "could", "you",
        "we", "they", "our", "your", "this", "that", "it", "as", "by",
        "from", "up", "about", "into", "than", "more", "also", "must",
        "strong", "good", "experience", "knowledge", "understanding", "ability",
        "work", "working", "including", "such", "well", "required", "preferred"
    }

    # Tokenize: lowercase, split on non-alphanumeric, filter stopwords + short tokens
    words = re.findall(r'[a-zA-Z0-9#\+\.\/]+', description.lower())
    keywords = [w for w in words if w not in stopwords and len(w) > 2]

    # Deduplicate while preserving order
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique_keywords.append(kw)

    return unique_keywords


# ───────────────────────────────────────────────────────────────
# STEP 3A: Keyword Matching Score (50 points)
# Compare resume text against the required skills for the role.
# ───────────────────────────────────────────────────────────────
def score_keywords(resume_text_lower, required_skills):
    """
    Returns:
        - score (0-50): proportional to % of skills matched
        - matched: list of found skills
        - missing: list of not-found skills
    """
    matched = []
    missing = []

    for skill in required_skills:
        # Use word-boundary search for multi-word skills too
        pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, resume_text_lower):
            matched.append(skill)
        else:
            missing.append(skill)

    # Score is proportional: (matched / total) * 50
    if len(required_skills) == 0:
        return 0, matched, missing

    score = round((len(matched) / len(required_skills)) * 50)
    return score, matched, missing


# ───────────────────────────────────────────────────────────────
# STEP 3B: Section Detection Score (20 points)
# Checks if the resume contains the 4 essential sections.
# 5 points per section detected.
# ───────────────────────────────────────────────────────────────
def score_sections(resume_text_lower):
    """
    Returns:
        - score (0-20): 5 points per detected section
        - detected_sections: list of found section names
        - missing_sections: list of sections not found
    """
    detected = []
    missing  = []

    for section, keywords in SECTION_KEYWORDS.items():
        found = any(kw in resume_text_lower for kw in keywords)
        if found:
            detected.append(section)
        else:
            missing.append(section)

    score = len(detected) * 5  # 5 points each, max 20
    return score, detected, missing


# ───────────────────────────────────────────────────────────────
# STEP 3C: Action Words Score (20 points)
# Strong action verbs signal active contributions.
# ───────────────────────────────────────────────────────────────
def score_action_words(resume_text_lower):
    """
    Returns:
        - score (0-20): based on how many unique action words appear
        - found_words: list of matching action words
    """
    found_words = []
    for word in ACTION_WORDS:
        if re.search(r'\b' + word + r'\b', resume_text_lower):
            found_words.append(word)

    # Score: up to 20 points. Each word is worth ~1.5 pts, capped at 20.
    score = min(len(found_words) * 2, 20)
    return score, found_words


# ───────────────────────────────────────────────────────────────
# STEP 3D: Resume Length Score (10 points)
# Ideal range: 300–800 words. Too short or too long = deductions.
# ───────────────────────────────────────────────────────────────
def score_length(resume_text):
    """
    Returns:
        - score (0-10): full points for 300-800 words
        - word_count: number of words
        - length_comment: human-readable feedback
    """
    words = resume_text.split()
    word_count = len(words)

    if 300 <= word_count <= 800:
        score   = 10
        comment = f"Good length ({word_count} words). Ideal range is 300–800 words."
    elif word_count < 150:
        score   = 2
        comment = f"Too short ({word_count} words). Add more detail to your experience and projects."
    elif word_count < 300:
        score   = 6
        comment = f"Slightly short ({word_count} words). Consider expanding your descriptions."
    elif word_count <= 1200:
        score   = 7
        comment = f"Slightly long ({word_count} words). Try to keep it under 800 words."
    else:
        score   = 4
        comment = f"Too long ({word_count} words). Recruiters prefer concise resumes."

    return score, word_count, comment


# ───────────────────────────────────────────────────────────────
# STEP 4: Build Strengths & Weaknesses from scores
# ───────────────────────────────────────────────────────────────
def build_strengths_weaknesses(
    keyword_score, action_score, section_score, length_score,
    matched_skills, missing_sections, word_count, found_action_words
):
    strengths  = []
    weaknesses = []

    # ── Keyword feedback ──
    if keyword_score >= 35:
        strengths.append(f"Strong skill match with {len(matched_skills)} relevant skills found.")
    elif keyword_score >= 20:
        strengths.append(f"Moderate skill match — {len(matched_skills)} relevant skills detected.")
    else:
        weaknesses.append("Low keyword match. Many required skills for this role are missing.")

    # ── Action words feedback ──
    if action_score >= 14:
        strengths.append(f"Excellent use of action verbs ({len(found_action_words)} found). Resume sounds proactive.")
    elif action_score >= 8:
        strengths.append(f"Decent use of action words ({len(found_action_words)} found).")
    else:
        weaknesses.append("Weak use of action verbs. Use words like 'Built', 'Developed', 'Implemented'.")

    # ── Section feedback ──
    if section_score == 20:
        strengths.append("All key resume sections are present (Education, Skills, Projects, Experience).")
    else:
        for s in missing_sections:
            weaknesses.append(f"Missing '{s.capitalize()}' section — this is important for recruiters.")

    # ── Length feedback ──
    if length_score == 10:
        strengths.append(f"Resume length is ideal ({word_count} words).")
    elif word_count < 300:
        weaknesses.append(f"Resume is too short ({word_count} words). Add more content.")
    else:
        weaknesses.append(f"Resume length ({word_count} words) is outside the ideal 300–800 word range.")

    return strengths, weaknesses


# ───────────────────────────────────────────────────────────────
# STEP 5: Pick recommendations based on role + missing skills
# ───────────────────────────────────────────────────────────────
def build_recommendations(job_role, missing_skills):
    recs = []

    # Generic missing-skill suggestions
    if missing_skills:
        top_missing = missing_skills[:5]  # show top 5
        recs.append(f"Add these missing skills to your resume: {', '.join(top_missing)}.")

    # Role-specific advice
    role_recs = ROLE_RECOMMENDATIONS.get(job_role.lower(), [])
    recs.extend(role_recs[:4])  # add up to 4 role-specific tips

    # Generic always-helpful tips
    recs.append("Quantify your achievements with numbers (e.g., 'improved performance by 40%').")
    recs.append("Tailor your resume for each job application for best results.")

    return recs


# ═══════════════════════════════════════════════════════════════
# MAIN — Entry point
# ═══════════════════════════════════════════════════════════════
def analyze_resume(pdf_path, job_role, custom_description=""):
    """
    Full pipeline:
    1. Extract text from PDF
    2. Determine required skills (from role or custom description)
    3. Score on 4 criteria
    4. Build result object
    """

    # 1. Extract text
    resume_text       = extract_text_from_pdf(pdf_path)
    resume_text_lower = resume_text.lower()

    # 2. Determine required skills
    if custom_description.strip():
        # Smart extraction from custom job description
        required_skills = extract_keywords_from_description(custom_description)
        # Limit to 20 most relevant keywords to keep scoring fair
        required_skills = required_skills[:20]
        effective_role  = "custom"
    else:
        # Use predefined role skill set
        job_role_key    = job_role.lower().strip()
        required_skills = JOB_ROLES.get(job_role_key, JOB_ROLES["software developer"])
        effective_role  = job_role_key

    # 3. Score each category
    keyword_score,  matched_skills, missing_skills = score_keywords(resume_text_lower, required_skills)
    section_score,  detected_sections, missing_sections = score_sections(resume_text_lower)
    action_score,   found_action_words = score_action_words(resume_text_lower)
    length_score,   word_count, length_comment = score_length(resume_text)

    # 4. Final score (weighted sum)
    final_score = keyword_score + section_score + action_score + length_score

    # 5. Build human-readable feedback
    strengths, weaknesses = build_strengths_weaknesses(
        keyword_score, action_score, section_score, length_score,
        matched_skills, missing_sections, word_count, found_action_words
    )

    # 6. Recommendations
    recommendations = build_recommendations(effective_role, missing_skills)

    # 7. Compose final result
    result = {
        "score":           final_score,          # 0-100
        "matched_skills":  matched_skills,        # skills found in resume
        "missing_skills":  missing_skills,        # skills not found
        "strengths":       strengths,             # positive points
        "weaknesses":      weaknesses,            # areas to improve
        "recommendations": recommendations,       # actionable tips
        "breakdown": {
            "keyword_score":  keyword_score,      # /50
            "section_score":  section_score,      # /20
            "action_score":   action_score,       # /20
            "length_score":   length_score,       # /10
            "word_count":     word_count,
            "length_comment": length_comment,
            "action_words_found": found_action_words,
            "sections_found": detected_sections
        }
    }

    return result


# ═══════════════════════════════════════════════════════════════
# Script entry point — called by Node.js via child_process.spawn
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: analyze.py <pdf_path> <job_role> [custom_description]"}))
        sys.exit(1)

    pdf_path           = sys.argv[1]
    job_role           = sys.argv[2]
    custom_description = sys.argv[3] if len(sys.argv) > 3 else ""

    try:
        result = analyze_resume(pdf_path, job_role, custom_description)
        # Output JSON to stdout — Node.js reads this
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
