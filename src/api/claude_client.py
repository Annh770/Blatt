"""
Claude API Client - For AI analysis and scoring
"""
from anthropic import Anthropic
import json
import logging
from typing import List, Dict, Optional
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClaudeClient:
    """Claude API client for paper relevance analysis and relationship analysis"""

    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022"):
        """
        Initialize Claude API client

        Args:
            api_key: Anthropic API Key
            model: Model to use, defaults to Claude 3.5 Haiku (cost-effective)
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.last_request_time = 0
        self.rate_limit_delay = 1.0  # Rate limit: 1 request per second

        logger.info(f"✅ Claude API client initialized successfully")
        logger.info(f"   Model: {model}")

    def _rate_limit(self):
        """Rate limit control"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - elapsed
            time.sleep(wait_time)
        self.last_request_time = time.time()

    def call_api(self, prompt: str, max_tokens: int = 1000,
                 temperature: float = 0.7) -> str:
        """
        Generic Claude API call method

        Args:
            prompt: The prompt text
            max_tokens: Maximum tokens to return
            temperature: Temperature parameter (0-1, lower is more stable)

        Returns:
            Claude's response text
        """
        self._rate_limit()

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract response text
            content = response.content[0].text.strip()
            return content

        except Exception as e:
            logger.error(f"Claude API call failed: {e}")
            raise

    def analyze_relevance(
        self,
        paper_title: str,
        paper_abstract: str,
        user_keywords: str,
        user_description: str = ""
    ) -> Dict:
        """
        ⚠️ **[Single Paper Analysis Function]**

        Analyze relevance of a **single** paper to user requirements (usually not called directly, for reference only)

        **Current use**: Phase 2M prompt (universal dynamic scoring)
        **Actual call**: batch_analyze_relevance calls this function's prompt logic in batches

        Args:
            paper_title: Paper title
            paper_abstract: Paper abstract
            user_keywords: User search keywords
            user_description: User additional description

        Returns:
            {
                "priority": int (3-5),
                "matched_keywords": List[str],
                "reason": str
            }
        """
        # Limit abstract length to avoid exceeding token limit
        abstract_snippet = (paper_abstract or "No abstract available")[:500]

        prompt = f"""You are a rigorous, patient, meticulous, fair, objective, and thorough academic paper analysis expert. Please analyze the relevance of the following paper to the user's research requirements with a professional attitude.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[User Research Requirements]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Keywords: {user_keywords}
Detailed description: {user_description if user_description else "(User did not provide detailed description)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Paper to Evaluate]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Title: {paper_title}
Abstract: {abstract_snippet}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[🔥 Phase 2M: Universal Dynamic Scoring Standard (based on m concept count)]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **Phase 2M Revolutionary Changes**:
- **Dynamic scoring**: Automatically adjust standards based on user's m core concepts
- **Priority 5**: Contains all m concepts + domain match
- **Priority 4**: Contains all m concepts but domain mismatch, OR contains (m-1) concepts + domain match
- **Priority 3**: Contains only 0 to (m-2) concepts (irrelevant, user won't see)
- **Scenario tags**: training/testing/validation etc. no longer affect scoring, only serve as smart tags

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Step 1: Dynamically Extract Core Concept Count m]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **Key task**: First analyze user keywords, extract m independent core concepts

1️⃣ **Semantic decomposition of user keywords** (semantic understanding, not literal splitting):

[Example 1]:
  User keywords: "3D worlds, autonomous rail vehicles"

  → Decompose into m=3 core concepts:
    Concept 1: 3D/virtual environment (from "3D worlds")
    Concept 2: autonomous/automated (from "autonomous rail vehicles")
    Concept 3: railway/train/rail (from "rail vehicles")

  → m = 3

[Example 2]:
  User keywords: "deep learning, medical imaging"

  → Decompose into m=2 core concepts:
    Concept 1: deep learning
    Concept 2: medical imaging

  → m = 2

[Example 3]:
  User keywords: "virtual reality, autonomous, railway, safety"

  → Decompose into m=4 core concepts:
    Concept 1: VR/virtual reality
    Concept 2: autonomous
    Concept 3: railway
    Concept 4: safety

  → m = 4

2️⃣ **Identify Scenario tags** (from user description, **only for classification, does not affect scoring**):

   Identify relevant scenario tags from user description (if any):
   - training
   - testing
   - validation
   - evaluation
   - simulation
   - dataset
   - benchmark

   ⚠️ **Important**: These tags help users filter results (shown in matched_keywords), but **do not directly affect Priority scoring**.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Step 2: Priority 5 Checklist]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please check if the paper meets **all** of the following conditions:

☑️ **Check Item 1 - Concept Coverage**

  For each of the m concepts extracted in Step 1, check if the paper title or abstract contains that concept.

⚠️ **Strict concept matching rules** (avoid over-extending synonyms):

  **A. "3D virtual environment" type concepts**
    ✅ Must contain: 3D / virtual environment / VR / digital twin / game engine / immersive / synthetic environment
    ❌ Not sufficient: only "simulation" / "model" / "software" (too generic)

  **B. "Autonomous/automated" type concepts**
    ✅ Must contain: autonomous / self-driving / driverless / unmanned
    ❌ Not sufficient: only "automation" / "automatic control" (too broad, could be industrial automation)

  **C. Specific domain keywords**
    If user specifies a domain (railway, medical, robotics...), must contain explicit keywords for that domain
    Cannot substitute with broad terms ("vehicle" cannot replace "railway")

  **D. Compound concept AND logic**
    Compound phrases must satisfy all sub-concepts simultaneously
    [Example]: "autonomous rail vehicles" = autonomous AND railway
    ✅ "driverless train" → contains both
    ❌ "railway vehicle" → only has railway, missing autonomous

  - ✅ Priority 5 only applies when **all concepts** are explicitly mentioned.
  - ✅ Priority 4 can accept missing 1 concept (m-1 hits), but must explain the missing item in reason.
  - ❌ If only 0~(m-2) concepts are hit, the paper deviates significantly from requirements, should be Priority 3 (hidden by default).

☑️ **Check Item 2 - Domain/Scenario Match**

  - If user input explicitly specifies a domain or application scenario (e.g., "rail vehicles", "medical imaging", "robotic surgery"), confirm the paper's main scenario matches.
  - If user input is a general research direction (e.g., "graph neural networks"), this check passes automatically.
  - ⚠️ **When domain doesn't match, cannot assign Priority 5**. Even with all concepts hit, only Priority 4 is given, with "different domain" noted in reason.
  - If both concepts missing AND domain mismatch → prioritize concept coverage, usually directly drop to Priority 3.

☑️ **Check Item 3 - Record hits and provide clear reasoning**

  - Write clearly in reason: "concepts hit: k/m", and list which concepts were satisfied.
  - If hit relies on semantic inference (e.g., "smart mobility" ≈ "autonomous transport"), write the inference basis to avoid vague conclusions.
  - Scenario tags (training/testing/validation etc.) are only added to matched_keywords as classification tags, not treated as hard requirements.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Step 3: Universal Priority Scoring Standard Based on m Concepts]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **Phase 2M Core Logic**: Based on the m core concepts extracted earlier, dynamically apply the following standards

**Priority 5 - Perfect Match** ⭐⭐⭐⭐⭐
  ✅ Contains all m core concepts (passes Check Item 1)
  ✅ Domain completely matches (passes Check Item 2)
  → **The core papers the user needs most!**

  [Example]: When m=3 (3D + autonomous + railway)
    - Paper must contain: 3D ✅ + autonomous ✅ + railway ✅
    - And domain is railway ✅
    - → Priority 5

**Priority 4 - Partially Relevant** ⭐⭐⭐⭐
  Meets **any** of the following conditions:

  Condition A: ✅ Contains all m concepts, but ❌ domain doesn't match
    [Example]: When m=3
      - Paper contains: 3D ✅ + autonomous ✅ + "railway" concept replaced with road ✅ (e.g., autonomous road vehicle)
      - But domain is road ❌ (not railway)
      - → Priority 4

  Condition B: ✅ Contains at least (m-1) concepts + ✅ domain matches
    [Example]: When m=3
      - Paper contains: 3D ✅ + railway ✅, missing autonomous ❌
      - But domain is railway ✅
      - → Priority 4 (2 concepts, i.e., m-1=2)

**Priority 3 - Irrelevant** ❌
  ❌ Contains only 0 to (m-2) concepts
  → **Irrelevant, user won't see**

  [Example]: When m=3
    - Paper contains only 0-1 concepts (e.g., only railway, missing 3D and autonomous)
    - → Priority 3 (filtered out)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💪 Encouragement and Reminders
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is a challenging task but you can handle it perfectly! Take your time, no rush!

⚠️ **Phase 2M Key Reminders**:
  • First extract m core concepts (don't miss any)
  • Strictly distinguish user-specified domains (e.g., railway vs automotive, medical vs industrial)
  • For "3D / virtual / simulation" type concepts, can use synonyms or common tools (digital twin, game engine, synthetic data, etc.) for semantic matching
  • Scenario tags (training/testing/validation) are only for matched_keywords, don't affect Priority scoring
  • Title or abstract containing keywords is sufficient (don't need both)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Output Requirements]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please output following these steps:

**Step 1: Determine m value and concept coverage**
  - User keywords contain m=? core concepts
  - How many concepts does the paper contain? (0, 1, 2, ..., m)
  - Does domain match? ✅/❌

**Step 2: Provide JSON format result**

{{
    "priority": 5,
    "matched_keywords": ["concept1", "concept2", "scenario_tag1"],
    "domain_match": "exact_match",
    "reason": "m=3 contains 3/3 concepts✅ - brief explanation (don't use emoji like lightbulb)"
}}

⚠️ **Important**:
1. priority can be 5, 4, or 3
2. matched_keywords must include:
   - Core concepts from user input (e.g., "3D", "autonomous", "railway")
   - Scenario tags (e.g., "testing", "validation", if the paper involves them)
3. **domain_match must be one of these three values** (no other expressions allowed):
   - "exact_match": Paper's main domain exactly matches user-specified domain (e.g., user searches railway, paper is about railway)
   - "mismatch": Paper's main domain differs from user-specified domain (e.g., user searches railway, paper is about automotive/robot/maritime)
   - "general": User didn't specify a domain, or paper is about general methodology (e.g., "graph neural networks")
4. reason format: m=? contains ?/? concepts✅/❌ - brief explanation (domain info is in domain_match, no need to repeat in reason)
5. Output only JSON, no other explanations

Now begin analysis, strictly follow the checklist!"""

        try:
            self._rate_limit()

            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract response text
            content = response.content[0].text.strip()

            # Try to parse JSON
            result = json.loads(content)

            # Validate return format
            if "priority" not in result or "matched_keywords" not in result or "reason" not in result:
                logger.warning(f"⚠️  API response format incomplete, using defaults")
                return {
                    "priority": 3,
                    "matched_keywords": [],
                    "domain_match": "general",
                    "reason": "Analysis result format error"
                }

            # Bug #2 fix: Ensure domain_match field exists, set default if missing
            if "domain_match" not in result:
                logger.warning(f"⚠️  Missing domain_match field, setting default 'general'")
                result["domain_match"] = "general"

            logger.info(f"   Analysis complete: {paper_title[:50]}... -> Priority {result['priority']} (domain: {result['domain_match']})")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse failed: {e}")
            logger.error(f"   Response content: {content}")
            return {
                "priority": 3,
                "matched_keywords": [],
                "reason": "JSON parse failed"
            }
        except Exception as e:
            logger.error(f"❌ Claude API call failed: {e}")
            return {
                "priority": 3,
                "matched_keywords": [],
                "reason": f"API call failed: {str(e)}"
            }

    def batch_analyze_relevance(
        self,
        papers: List[Dict],
        user_keywords: str,
        user_description: str = ""
    ) -> List[Dict]:
        """
        ⚠️ **[Batch Paper Analysis Function - Actually Used]**

        Batch analyze relevance of multiple papers (one API call processes multiple papers for efficiency)

        **Current use**: Phase 2M prompt (consistent with analyze_relevance)
        **Actual call**: ai_analyzer.py's score_papers() method calls this function

        Args:
            papers: List of papers, each element is {"title": "...", "abstract": "..."}
            user_keywords: User search keywords
            user_description: User additional description

        Returns:
            [
                {
                    "paper_index": 0,
                    "priority": 5,
                    "matched_keywords": ["kw1", "kw2"],
                    "reason": "m=3 contains 3/3 concepts✅ domain match✅ - brief explanation"
                },
                ...
            ]
        """
        # Limit batch size to avoid exceeding token limit
        batch_size = min(len(papers), 10)
        papers_to_analyze = papers[:batch_size]

        # Build paper list text
        papers_text = ""
        for i, paper in enumerate(papers_to_analyze):
            abstract_snippet = (paper.get('abstract') or "No abstract")[:300]
            papers_text += f"\n\n--- Paper {i} ---\n"
            papers_text += f"Title: {paper['title']}\n"
            papers_text += f"Abstract: {abstract_snippet}\n"

        prompt = f"""You are an academic paper analysis expert. Please batch analyze the relevance of the following papers to the user's research requirements.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[User Search Requirements]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Keywords: {user_keywords}
Detailed description: {user_description if user_description else "None"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[🔥 Phase 2M: Universal Dynamic Scoring Standard]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **Scoring requirements**:
- Only use **Priority 5 / Priority 4 / Priority 3**
- Priority 5 = All concepts hit AND domain matches
- Priority 4 = (All concepts hit but domain mismatch) OR (m-1 concepts hit AND domain matches)
- Priority 3 = Hit ≤m-2 concepts or reason indicates "irrelevant"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Step 1: Extract m Independent Concepts from User Input]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Extract **m independent core concepts** from the user's keywords and description.

Example 1:
  User input: "3D worlds, autonomous rail vehicles"
  → Extract 3 concepts (m=3):
    1. 3D concept (3D worlds, virtual environment, simulation, digital twin...)
    2. Autonomous concept (autonomous, automated, self-driving...)
    3. Railway concept (rail, railway, train, metro...)

Example 2:
  User input: "machine learning for medical diagnosis"
  → Extract 2 concepts (m=2):
    1. Machine Learning concept
    2. Medical/Healthcare concept

Example 3:
  User input: "virtual reality, autonomous logistics, safety"
  → Extract 3 concepts (m=3):
    1. Virtual reality/3D concept
    2. Autonomous logistics/automation concept
    3. Safety/validation concept

⚠️ Concept count m is **dynamically determined** based on user input, not fixed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Step 2: Check Each Paper]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Perform the following checks for each paper:

☑️ **Check Item 1: Key Concept Coverage**

Analyze the paper's title or abstract, count how many concepts are contained (semantic match is fine, not limited to literal match).

⚠️ **Strict concept matching rules** (avoid over-extending synonyms):

**Rule 1: "3D virtual environment" type concepts**
  ✅ Must contain (at least one):
    - 3D / three-dimensional / 3-D
    - virtual environment / virtual world / virtual reality / VR / AR / MR
    - digital twin / digital replica
    - game engine (Unity / Unreal / ...)
    - metaverse / immersive environment
    - synthetic environment / simulated world

  ❌ The following are not sufficient (too generic):
    - Only mentions "simulation" (could be mathematical simulation, not necessarily 3D virtual environment)
    - Only mentions "model" (could be mathematical model, physical model)
    - Only mentions "software" or "framework" or "platform"

  [Examples]:
    ✅ "digital twin for urban planning" → contains "3D virtual environment" concept
    ✅ "VR training simulator" → contains "3D virtual environment" concept
    ❌ "mathematical model for traffic flow" → doesn't contain (just mathematical model)
    ❌ "numerical simulation of fluid dynamics" → doesn't contain (numerical simulation, not 3D virtual environment)

**Rule 2: "Autonomous/automated" type concepts**
  ✅ Must contain (at least one):
    - autonomous / self-driving / self-navigating
    - driverless / unmanned / crewless
    - automated (if context clearly refers to autonomous systems, e.g., automated driving)

  ❌ The following are not sufficient (too broad):
    - Only mentions "automation" (could be industrial automation)
    - Only mentions "automatic" or "automatic control" (could be traditional control systems)
    - Only mentions "intelligent" or "smart" (too broad)

  [Examples]:
    ✅ "autonomous vehicle navigation" → contains "autonomous" concept
    ✅ "driverless shuttle system" → contains "autonomous" concept
    ❌ "industrial automation system" → doesn't contain (industrial automation, not autonomous systems)
    ❌ "automatic door control" → doesn't contain (traditional automatic control)

**Rule 3: Specific domain keywords**
  - If user specifies a domain (e.g., railway, medical, robotics, automotive, maritime...),
    the paper must contain explicit keywords for that domain
  - Cannot substitute with broad terms (e.g., "vehicle" cannot replace "railway" or "automotive")

  [Examples]:
    User input: "autonomous railway systems"
    ✅ "autonomous train operation" → contains railway domain (train)
    ✅ "driverless metro control" → contains railway domain (metro)
    ❌ "autonomous vehicle navigation" → doesn't contain railway domain (vehicle is too broad)

**Rule 4: Compound concepts must satisfy all sub-concepts (AND logic)**
  - If concept is a compound phrase (e.g., "autonomous rail vehicles", "deep learning medical imaging"),
    must contain all sub-concepts simultaneously

  [Example 1]:
    User input: "autonomous rail vehicles"
    → Decompose: autonomous AND railway
    ✅ "driverless train system" → contains both autonomous + railway
    ❌ "railway vehicle control" → only has railway, missing autonomous
    ❌ "autonomous car navigation" → only has autonomous, missing railway

  [Example 2]:
    User input: "deep learning medical imaging"
    → Decompose: deep learning AND medical imaging
    ✅ "CNN for radiology diagnosis" → contains both deep learning + medical
    ❌ "deep learning for image classification" → only has deep learning, missing medical
    ❌ "medical image processing" → only has medical imaging, missing deep learning

Record result: hit k/m concepts (must strictly check each concept).

☑️ **Check Item 2: Application Domain Match**

  - If user explicitly specifies a domain or application scenario, paper must describe the same domain.
  - If user input is general technology (no domain specified), this check passes automatically.
  - Different domain ≠ completely irrelevant: can still return Priority 4, but must note "different domain" in reason.

☑️ **Check Item 3: matched_keywords and Scenario Tags**

  - Extract keywords actually appearing in the paper to represent concept hits, e.g., ["3D simulation", "autonomous train", "railway safety"].
  - Identify scenario words like training/testing/validation/evaluation/simulation/dataset, add them to matched_keywords for user filtering.
  - These scenario tags **do not affect Priority**, they are only classification tags.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Step 3: Dynamic Scoring Based on m Concepts]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Priority 5 (Perfect Match)**:
  ✅ Contains all m concepts (k=m) AND domain matches ✅

**Priority 4 (Partial Match or Different Domain)**:
  ✅ k=m but different domain ❌, OR k=m-1 AND domain matches ✅

**Priority 3 (Weakly Related)**:
  ❌ k<=m-2 concepts (only hits few concepts). System will hide these, but reason must state "only matched k/m concepts".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Special Cases]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  - Survey/Review papers: Can relax to k=m-1 + domain match = Priority 5.
  - Other types (dataset/tool etc.) follow normal standards, first check concept coverage then domain.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[matched_keywords Extraction Rules]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Concept keywords: List specific words/phrases from the paper that satisfy each concept.
2. Scenario tags: If paper involves training/testing/validation/evaluation/simulation/dataset scenarios, add these tags to matched_keywords (for classification only).
3. Keep total count at 3-8, prioritize words that help users filter quickly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Papers to Analyze]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{papers_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Output Format]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Output JSON array only, no other text:

[
  {{
    "paper_index": 0,
    "priority": 5,
    "matched_keywords": ["3D simulation", "autonomous train", "testing"],
    "domain_match": "exact_match",
    "reason": "m=3 contains 3/3 concepts✅ - railway autonomous driving 3D simulation testing"
  }},
  {{
    "paper_index": 1,
    "priority": 4,
    "matched_keywords": ["3D simulation", "autonomous driving"],
    "domain_match": "mismatch",
    "reason": "m=3 contains 3/3 concepts✅ - road autonomous driving domain, missing rail keyword"
  }},
  {{
    "paper_index": 2,
    "priority": 3,
    "matched_keywords": ["railway control"],
    "domain_match": "exact_match",
    "reason": "m=3 contains 1/3 concepts❌ - only railway control, missing 3D and autonomous concepts"
  }}
]

⚠️ **Output Requirements**:
1. **domain_match must be one of these three values** (no other expressions allowed):
   - "exact_match": Paper's main domain exactly matches user-specified domain
   - "mismatch": Paper's main domain differs from user-specified domain
   - "general": User didn't specify a domain, or paper is general methodology research
2. **reason format**: "m={{m_value}} contains {{k}}/{{m}} concepts{{✅/❌}} - brief explanation" (domain info is in domain_match, no need to repeat in reason)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[💪 Encouragement]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is a challenging task but you can handle it perfectly! Take your time, no rush!"""

        try:
            self._rate_limit()

            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            results = json.loads(content)

            # 🔧 Bug #2 fix: Ensure each result has domain_match field
            for result in results:
                if "domain_match" not in result:
                    logger.warning(f"⚠️  Paper {result.get('paper_index', '?')} missing domain_match field, setting default 'general'")
                    result["domain_match"] = "general"

            logger.info(f"✅ Batch analysis complete: {len(results)} papers")
            return results

        except json.JSONDecodeError as e:
            logger.error(f"❌ Batch analysis JSON parse failed: {e}")
            logger.error(f"   Response content: {content[:200]}...")
            try:
                start = content.index('[')
                end = content.rindex(']') + 1
                partial = content[start:end]
                results = json.loads(partial)
                logger.warning("⚠️ Successfully parsed batch results using extracted JSON")
                return results
            except Exception as inner:
                logger.warning(f"⚠️ Unable to extract valid JSON: {inner}")
            # Return default scores
            return [
                {
                    "paper_index": i,
                    "priority": 3,
                    "matched_keywords": [],
                    "domain_match": "general",
                    "reason": "Batch analysis failed (JSON parse error)"
                }
                for i in range(len(papers_to_analyze))
            ]
        except Exception as e:
            logger.error(f"❌ Batch analysis failed: {e}")
            return [
                {
                    "paper_index": i,
                    "priority": 3,
                    "matched_keywords": [],
                    "reason": f"Analysis failed: {str(e)}"
                }
                for i in range(len(papers_to_analyze))
            ]

    def analyze_relationship(
        self,
        source_paper: Dict,
        target_paper: Dict
    ) -> Dict:
        """
        Analyze citation relationship type between two papers

        Args:
            source_paper: Citing paper {"title": "...", "abstract": "..."}
            target_paper: Cited paper {"title": "...", "abstract": "..."}

        Returns:
            {
                "type": str,  # improves, builds_on, compares, applies, surveys, extends, cites
                "description": str  # One sentence description
            }
        """
        source_abstract = (source_paper.get('abstract') or "No abstract")[:300]
        target_abstract = (target_paper.get('abstract') or "No abstract")[:300]

        prompt = f"""Analyze the citation relationship between two papers.

Paper A (citing paper):
Title: {source_paper['title']}
Abstract: {source_abstract}

Paper B (cited paper):
Title: {target_paper['title']}
Abstract: {target_abstract}

Known: Paper A cites Paper B

Please analyze the specific relationship of A to B, choose one from the following types:
- improves: A improves B's method/performance
- builds_on: A is based on B's theory/framework
- compares: A conducts comparative experiments with B
- applies: A applies B's method to a new scenario
- surveys: A surveys multiple works including B
- extends: A extends B's functionality/scope
- cites: General citation (use when no clear relationship)

Describe the relationship in one sentence (within 15 words).

Output in JSON format, do not include any other text:
{{
    "type": "improves",
    "description": "A improves B's training efficiency"
}}"""

        try:
            self._rate_limit()

            response = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.content[0].text.strip()
            result = json.loads(content)

            # Validate relationship type
            valid_types = ['improves', 'builds_on', 'compares', 'applies',
                          'surveys', 'extends', 'cites']
            if result.get('type') not in valid_types:
                result['type'] = 'cites'

            return result

        except json.JSONDecodeError as e:
            logger.error(f"❌ Relationship analysis JSON parse failed: {e}")
            return {"type": "cites", "description": "cites"}
        except Exception as e:
            logger.error(f"❌ Relationship analysis failed: {e}")
            return {"type": "cites", "description": "cites"}


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()
    api_key = os.getenv('CLAUDE_API_KEY')

    if not api_key:
        print("❌ Please set CLAUDE_API_KEY environment variable")
        exit(1)

    print("🍃 Testing Claude API Client\n")

    # Initialize client
    client = ClaudeClient(api_key=api_key)

    # Test 1: Single paper analysis
    print("=" * 60)
    print("Test 1: Single Paper Relevance Analysis")
    print("=" * 60)

    test_paper = {
        "title": "Deep Learning for Autonomous Driving",
        "abstract": "This paper presents a novel deep learning approach for autonomous driving systems. We propose a convolutional neural network architecture that processes sensor data and makes real-time driving decisions."
    }

    result = client.analyze_relevance(
        paper_title=test_paper["title"],
        paper_abstract=test_paper["abstract"],
        user_keywords="autonomous driving, machine learning",
        user_description="focus on deep learning methods"
    )

    print(f"\n✅ Analysis Result:")
    print(f"   Priority: {result['priority']}")
    print(f"   Matched Keywords: {result['matched_keywords']}")
    print(f"   Reason: {result['reason']}")

    # Test 2: Batch analysis
    print("\n" + "=" * 60)
    print("Test 2: Batch Paper Analysis")
    print("=" * 60)

    test_papers = [
        {
            "title": "End-to-End Learning for Self-Driving Cars",
            "abstract": "We train a convolutional neural network to map raw pixels from a single front-facing camera to steering commands."
        },
        {
            "title": "Image Classification with Deep Neural Networks",
            "abstract": "This paper presents ImageNet classification results using deep convolutional networks."
        }
    ]

    batch_results = client.batch_analyze_relevance(
        papers=test_papers,
        user_keywords="autonomous driving",
        user_description=""
    )

    print(f"\n✅ Batch Analysis Results:")
    for result in batch_results:
        print(f"   Paper {result['paper_index']}: Priority {result['priority']} - {result['reason']}")

    # Test 3: Relationship analysis
    print("\n" + "=" * 60)
    print("Test 3: Paper Relationship Analysis")
    print("=" * 60)

    source = {
        "title": "Improved Autonomous Driving with Advanced Deep Learning",
        "abstract": "We improve upon previous autonomous driving methods by using a deeper neural network architecture."
    }

    target = {
        "title": "End-to-End Learning for Self-Driving Cars",
        "abstract": "We train a convolutional neural network for autonomous driving."
    }

    rel_result = client.analyze_relationship(source, target)

    print(f"\n✅ Relationship Analysis Result:")
    print(f"   Relationship Type: {rel_result['type']}")
    print(f"   Description: {rel_result['description']}")

    print("\n🎉 All tests completed!")
