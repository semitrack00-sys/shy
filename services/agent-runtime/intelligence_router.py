import importlib.util
import re
from pathlib import Path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


services_path = Path(__file__).resolve().parents[1]

types_module = load_module(
    "shy_intelligence_types",
    services_path / "core" / "intelligence_types.py",
)

Capability = types_module.Capability
Complexity = types_module.Complexity
CodingTaskProfile = types_module.CodingTaskProfile
CodingTaskType = types_module.CodingTaskType
IntelligenceDecision = types_module.IntelligenceDecision
ReasonCode = types_module.ReasonCode


class IntelligenceRouter:
    """
    Phase 1 capability router.

    This router performs deterministic capability classification.
    It does not execute tools and does not call an LLM.
    """

    def analyze(self, message: str) -> IntelligenceDecision:
        text = " ".join(message.lower().split())

        if not text:
            return IntelligenceDecision(
                primary_capability=Capability.CHAT,
                complexity=Complexity.SIMPLE,
                confidence=0.5,
                reason_code=ReasonCode.SIMPLE_CONVERSATION,
            )

        if self._is_explicit_tool_request(text):
            return IntelligenceDecision(
                primary_capability=Capability.TOOL,
                complexity=Complexity.MODERATE,
                requires_tool=True,
                confidence=0.93,
                reason_code=ReasonCode.TOOL_REQUIRED,
            )

        if self._is_research_request(text):
            reason_code = ReasonCode.EXPLICIT_RESEARCH_REQUEST

            if self._needs_current_information(text):
                reason_code = ReasonCode.CURRENT_INFORMATION_REQUIRED

            return IntelligenceDecision(
                primary_capability=Capability.RESEARCH,
                secondary_capabilities=(Capability.REASONING,),
                complexity=Complexity.MODERATE,
                requires_external_evidence=True,
                requires_tool=True,
                verification_required=True,
                confidence=0.92,
                reason_code=reason_code,
            )

        if self._is_memory_request(text):
            return IntelligenceDecision(
                primary_capability=Capability.MEMORY,
                secondary_capabilities=(Capability.CHAT,),
                complexity=Complexity.MODERATE,
                requires_memory=True,
                confidence=0.84,
                reason_code=ReasonCode.MEMORY_CONTEXT_REQUIRED,
            )

        coding_profile = self._classify_coding_task(text)
        if coding_profile is not None:
            secondary = (Capability.REASONING,)
            if coding_profile.complexity == Complexity.COMPLEX:
                secondary = (Capability.REASONING, Capability.MULTI_STEP)

            return IntelligenceDecision(
                primary_capability=Capability.CODING,
                secondary_capabilities=secondary,
                complexity=coding_profile.complexity,
                verification_required=coding_profile.verification_required,
                repository_context_required=coding_profile.repository_context_required,
                execution_required=coding_profile.execution_required,
                coding_profile=coding_profile,
                confidence=0.9 if coding_profile.task_type != CodingTaskType.UNKNOWN else 0.72,
                reason_code=coding_profile.reason_code,
            )

        if self._is_coding_false_positive(text):
            return IntelligenceDecision(
                primary_capability=Capability.CHAT,
                complexity=Complexity.SIMPLE,
                confidence=0.74,
                reason_code=ReasonCode.SIMPLE_CONVERSATION,
            )

        if self._is_multi_step_request(text):
            return IntelligenceDecision(
                primary_capability=Capability.MULTI_STEP,
                secondary_capabilities=(Capability.REASONING,),
                complexity=Complexity.COMPLEX,
                verification_required=True,
                confidence=0.9,
                reason_code=ReasonCode.MULTI_CONSTRAINT_TASK,
            )

        if self._is_reasoning_request(text):
            return IntelligenceDecision(
                primary_capability=Capability.REASONING,
                complexity=Complexity.MODERATE,
                verification_required=True,
                confidence=0.78,
                reason_code=ReasonCode.MULTI_CONSTRAINT_TASK,
            )

        return IntelligenceDecision(
            primary_capability=Capability.CHAT,
            complexity=Complexity.SIMPLE,
            confidence=0.72,
            reason_code=ReasonCode.SIMPLE_CONVERSATION,
        )

    @staticmethod
    def _is_explicit_tool_request(text: str) -> bool:
        tool_terms = (
            "use system health",
            "system health",
            "check your health",
            "run tool",
        )
        return any(term in text for term in tool_terms)

    @staticmethod
    def _is_research_request(text: str) -> bool:
        research_terms = (
            "research ",
            "search the web",
            "search online",
            "look up ",
            "find online",
            "latest developments",
        )
        return any(term in text for term in research_terms)

    @staticmethod
    def _needs_current_information(text: str) -> bool:
        freshness_terms = (
            "latest",
            "current",
            "today",
            "recent",
            "developments",
        )
        return any(term in text for term in freshness_terms)

    @staticmethod
    def _is_memory_request(text: str) -> bool:
        memory_terms = (
            "as we discussed",
            "earlier in this conversation",
            "remember that",
            "from previous messages",
            "conversation context",
        )
        return any(term in text for term in memory_terms)

    @staticmethod
    def _is_coding_false_positive(text: str) -> bool:
        non_coding_phrases = (
            "dress code",
            "zip code",
            "postal code",
            "airport code",
            "medical billing code",
            "code red",
        )
        strong_coding_markers = (
            "python",
            "javascript",
            "typescript",
            "react",
            "api",
            "stack trace",
            "traceback",
            "exception",
            "unit test",
            "pytest",
            "jest",
            "git diff",
            "pull request",
            "repository",
            "codebase",
            "gradle",
            "build.gradle",
            "gradlew",
            "refactor",
            "debug",
        )
        return any(phrase in text for phrase in non_coding_phrases) and not any(
            marker in text for marker in strong_coding_markers
        )

    @staticmethod
    def _is_coding_request(text: str) -> bool:
        return IntelligenceRouter._classify_coding_task(text) is not None

    @staticmethod
    def _classify_coding_task(text: str) -> CodingTaskProfile | None:
        if not text:
            return None

        non_coding_phrases = (
            "dress code",
            "zip code",
            "postal code",
            "airport code",
            "medical billing code",
            "code red",
        )

        strong_coding_markers = (
            "python",
            "javascript",
            "typescript",
            "react",
            "api",
            "stack trace",
            "traceback",
            "exception",
            "unit test",
            "pytest",
            "jest",
            "git diff",
            "pull request",
            "repository",
            "codebase",
            "gradle",
            "build.gradle",
            "gradlew",
            "refactor",
            "debug",
        )

        if any(phrase in text for phrase in non_coding_phrases) and not any(
            marker in text for marker in strong_coding_markers
        ):
            return None

        languages = IntelligenceRouter._extract_languages(text)
        frameworks = IntelligenceRouter._extract_frameworks(text)

        task_profiles: tuple[tuple[CodingTaskType, tuple[str, ...]], ...] = (
            (
                CodingTaskType.REPOSITORY_ANALYSIS,
                ("repository", "codebase", "analyze project", "analyze repo", "architecture review"),
            ),
            (
                CodingTaskType.GIT_DIFF_REVIEW,
                ("git diff", "diff review", "review this diff", "pull request"),
            ),
            (
                CodingTaskType.REACT_BUILD_FAILURE,
                ("react", "vite", "webpack", "npm run build", "frontend build", "build failed"),
            ),
            (
                CodingTaskType.GRADLE_BUILD_FAILURE,
                ("gradle", "build.gradle", "gradlew", "jvm build", "android build failed"),
            ),
            (
                CodingTaskType.DEBUG_EXCEPTION,
                ("python exception", "throws exception", "exception", "crashes", "debug"),
            ),
            (
                CodingTaskType.STACK_TRACE_ANALYSIS,
                ("stack trace", "traceback", "line ", "error at "),
            ),
            (
                CodingTaskType.API_IMPLEMENTATION,
                ("api endpoint", "implement api", "rest api", "route handler", "controller"),
            ),
            (
                CodingTaskType.UNIT_TEST_GENERATION,
                ("unit test", "write tests", "test cases", "pytest", "jest"),
            ),
            (
                CodingTaskType.REFACTORING,
                ("refactor", "cleanup code", "clean up code", "improve readability"),
            ),
        )

        selected_task = CodingTaskType.UNKNOWN
        for task_type, markers in task_profiles:
            if any(marker in text for marker in markers):
                selected_task = task_type
                break

        weak_coding_terms = ("code", "function", "bug", "fix")
        has_strong_marker = any(marker in text for marker in strong_coding_markers)

        if selected_task == CodingTaskType.UNKNOWN and not has_strong_marker:
            if any(term in text for term in weak_coding_terms):
                return None
            return None

        repository_context_required = selected_task in {
            CodingTaskType.REACT_BUILD_FAILURE,
            CodingTaskType.GRADLE_BUILD_FAILURE,
            CodingTaskType.API_IMPLEMENTATION,
            CodingTaskType.UNIT_TEST_GENERATION,
            CodingTaskType.REFACTORING,
            CodingTaskType.GIT_DIFF_REVIEW,
            CodingTaskType.REPOSITORY_ANALYSIS,
        }

        execution_required = selected_task in {
            CodingTaskType.REACT_BUILD_FAILURE,
            CodingTaskType.GRADLE_BUILD_FAILURE,
            CodingTaskType.UNIT_TEST_GENERATION,
        }

        verification_required = selected_task in {
            CodingTaskType.DEBUG_EXCEPTION,
            CodingTaskType.STACK_TRACE_ANALYSIS,
            CodingTaskType.REACT_BUILD_FAILURE,
            CodingTaskType.GRADLE_BUILD_FAILURE,
            CodingTaskType.API_IMPLEMENTATION,
            CodingTaskType.UNIT_TEST_GENERATION,
            CodingTaskType.REFACTORING,
            CodingTaskType.GIT_DIFF_REVIEW,
            CodingTaskType.REPOSITORY_ANALYSIS,
        }

        complexity = Complexity.MODERATE
        if selected_task in {
            CodingTaskType.GIT_DIFF_REVIEW,
            CodingTaskType.REPOSITORY_ANALYSIS,
            CodingTaskType.REACT_BUILD_FAILURE,
            CodingTaskType.GRADLE_BUILD_FAILURE,
        }:
            complexity = Complexity.COMPLEX
        elif selected_task in {CodingTaskType.UNIT_TEST_GENERATION, CodingTaskType.API_IMPLEMENTATION}:
            complexity = Complexity.MODERATE
        elif selected_task == CodingTaskType.UNKNOWN:
            complexity = Complexity.MODERATE

        return CodingTaskProfile(
            task_type=selected_task,
            languages=languages,
            frameworks=frameworks,
            repository_context_required=repository_context_required,
            execution_required=execution_required,
            verification_required=verification_required,
            complexity=complexity,
            reason_code=ReasonCode.CODING_TASK_CLASSIFIED,
        )

    @staticmethod
    def _extract_languages(text: str) -> tuple[str, ...]:
        markers = (
            ("python", "python"),
            ("typescript", "typescript"),
            ("javascript", "javascript"),
            ("java", "java"),
            ("go", "go"),
            ("rust", "rust"),
        )
        languages = [name for marker, name in markers if re.search(rf"(^|[^a-z0-9]){re.escape(marker)}([^a-z0-9]|$)", text)]
        return tuple(dict.fromkeys(languages))

    @staticmethod
    def _extract_frameworks(text: str) -> tuple[str, ...]:
        markers = (
            ("react", "react"),
            ("fastapi", "fastapi"),
            ("django", "django"),
            ("flask", "flask"),
            ("pytest", "pytest"),
            ("jest", "jest"),
            ("gradle", "gradle"),
        )
        frameworks = [name for marker, name in markers if marker in text]
        return tuple(dict.fromkeys(frameworks))

    @staticmethod
    def _is_multi_step_request(text: str) -> bool:
        multi_step_terms = (
            "multi-stage",
            "multi step",
            "five constraints",
            "develop a plan",
            "implementation plan",
            "roadmap",
        )
        return any(term in text for term in multi_step_terms)

    @staticmethod
    def _is_reasoning_request(text: str) -> bool:
        reasoning_terms = (
            "compare",
            "tradeoff",
            "analyze",
            "strategy",
            "explain",
            "why",
        )
        return any(term in text for term in reasoning_terms)
