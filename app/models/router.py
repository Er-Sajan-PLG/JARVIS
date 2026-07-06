"""
Model Router for JARVIS v2.0

Routes requests to appropriate models based on task type.
"""

from enum import Enum
from typing import Dict, Optional

from app.models.client import ModelClient


class TaskType(Enum):
    AUTOCOMPLETE = "autocomplete"
    CODE = "code"
    REASONING = "reasoning"
    STEM = "stem"
    GENERAL = "general"
    DOCS = "docs"  # New task type for documentation-related tasks


class ModelRouter:
    """
    Routes requests to appropriate models.
    Uses score-based classification to avoid order bias.
    """
    
    # Keyword weights per task type (can be made configurable)
    KEYWORDS = {
        TaskType.CODE: [
            "code", "function", "class", "bug", "error", "debug", 
            "implement", "program", "script", "syntax", "compile",
            "refactor", "variable", "method", "algorithm", "api"
        ],
        TaskType.STEM: [
            "math", "calculate", "equation", "physics", "chemistry",
            "formula", "theorem", "proof", "derivative", "integral",
            "molecule", "atom", "force", "energy", "mass"
        ],
        TaskType.REASONING: [
            "think", "analyze", "reason", "logic", "compare",
            "evaluate", "justify", "argument", "conclusion", "premise",
            "deduce", "infer", "contradiction", "hypothesis"
        ],
    }
    
    def __init__(
        self,
        models: Dict[TaskType, ModelClient] = None,
        default_model: ModelClient = None
    ):
        self.models = models or {}
        self.default_model = default_model
    
    def register(self, task_type: TaskType, client: ModelClient):
        """Register a model for a specific task type"""
        self.models[task_type] = client
    
    def set_default(self, client: ModelClient):
        """Set the default model"""
        self.default_model = client
    
    def select(self, task_type: TaskType) -> ModelClient:
        """Select a model by explicit task type"""
        if task_type in self.models:
            return self.models[task_type]
        if self.default_model:
            return self.default_model
        raise ValueError(f"No model for task type: {task_type}")
    
    def route(self, prompt: str) -> tuple[ModelClient, TaskType]:
        """
        Automatically determine task type and select model.
        
        Returns:
            Tuple of (selected_model, detected_task_type)
        """
        task_type = self._classify_prompt(prompt)
        return self.select(task_type), task_type
    
    def _classify_prompt(self, prompt: str) -> TaskType:
        """
        Classify prompt into task type using score-based keyword matching.
        
        Uses scores instead of first-match to avoid order bias.
        """
        prompt_lower = prompt.lower()
        
        # Calculate scores for each task type
        scores: Dict[TaskType, int] = {}
        for task_type, keywords in self.KEYWORDS.items():
            scores[task_type] = sum(1 for kw in keywords if kw in prompt_lower)
        
        # Find the maximum score
        max_score = max(scores.values()) if scores else 0
        
        # If no keywords matched, default to GENERAL
        if max_score == 0:
            return TaskType.GENERAL
        
        # Get all task types with the max score
        top_types = [t for t, s in scores.items() if s == max_score]
        
        # If there's a single winner, use it
        if len(top_types) == 1:
            return top_types[0]
        
        # Tie-breaking: prefer more specific types over general ones
        # Order of specificity: CODE > STEM > REASONING > GENERAL
        preference_order = [TaskType.CODE, TaskType.STEM, TaskType.REASONING]
        for preferred in preference_order:
            if preferred in top_types:
                return preferred
        
        return TaskType.GENERAL