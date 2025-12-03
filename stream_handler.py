"""Streaming JSON parser handler for OrchestratorAnswer structured output"""

from jaxn import JSONParserHandler


class OrchestratorAnswerHandler(JSONParserHandler):
    def __init__(
        self,
        answer_container: object | None = None,
        confidence_container: object | None = None,
        reasoning_container: object | None = None,
        sources_container: object | None = None,
        agents_container: object | None = None,
    ):
        """
        Initialize handler with Streamlit containers for UI updates.

        Args:
            answer_container: st.empty() container for streaming answer text
            confidence_container: st.empty() container for confidence metric
            reasoning_container: st.empty() container for reasoning text
            sources_container: st.empty() container for sources list
            agents_container: st.empty() container for agents used list
        """
        super().__init__()
        self.answer_container = answer_container
        self.confidence_container = confidence_container
        self.reasoning_container = reasoning_container
        self.sources_container = sources_container
        self.agents_container = agents_container

        # Track state for incremental updates
        self.current_answer = ""
        self.current_confidence: float | None = None
        self.current_reasoning: str | None = None
        self.sources_list: list[str] = []
        self.agents_list: list[str] = []

        # Performance optimization: batch updates
        self._update_counter = 0
        self._update_interval = 10  # Update every N characters

    def reset(self) -> None:
        """Reset handler state for a new query"""
        self.current_answer = ""
        self.current_confidence = None
        self.current_reasoning = None
        self.sources_list = []
        self.agents_list = []
        self._update_counter = 0

    def on_field_start(self, path: str, field_name: str) -> None:
        """Called when starting to read a field value"""
        # Initialize arrays when starting
        if field_name == "sources_used" and path == "":
            self.sources_list = []
        elif field_name == "agents_used" and path == "":
            self.agents_list = []

    def on_field_end(
        self,
        path: str,
        field_name: str,
        value: object,
        parsed_value: object | None = None,
    ) -> None:
        """
        Called when a field value is complete.
        Update Streamlit UI components when fields finish.
        """
        if field_name == "answer" and path == "":
            # Ensure answer is fully displayed when field completes
            if self.answer_container and self.current_answer:
                self.answer_container.markdown(self.current_answer)

        elif field_name == "confidence" and path == "":
            # Display confidence as a metric
            self.current_confidence = float(value) if value is not None else None
            if self.confidence_container and self.current_confidence is not None:
                self.confidence_container.metric(
                    "Confidence", f"{self.current_confidence:.2%}"
                )

        elif field_name == "reasoning" and path == "":
            # Display reasoning when complete
            self.current_reasoning = str(value) if value is not None else None
            if self.reasoning_container and self.current_reasoning:
                self.reasoning_container.markdown(
                    f"**Reasoning:** {self.current_reasoning}"
                )

    def on_value_chunk(self, path: str, field_name: str, chunk: str) -> None:
        """
        Called for each character as string values stream in.
        Stream answer content as it arrives with batched updates for performance.
        """
        if field_name == "answer" and path == "":
            # Accumulate answer text
            self.current_answer += chunk
            # Update UI periodically (not on every character) for better performance
            self._update_counter += len(chunk)
            if self._update_counter >= self._update_interval and self.answer_container:
                self.answer_container.markdown(self.current_answer)
                self._update_counter = 0

    def on_array_item_end(
        self, path: str, field_name: str, item: object | None = None
    ) -> None:
        """
        Called when finishing an object in an array.
        Display sources and agents as they complete.
        """
        if path != "" or item is None:
            return

        if field_name == "sources_used":
            # Sources are strings in the array
            source = str(item).strip('"')
            if not source or source in self.sources_list:
                return

            self.sources_list.append(source)
            if self.sources_container:
                sources_text = "\n".join(f"- {s}" for s in self.sources_list)
                self.sources_container.markdown(f"**Sources:**\n{sources_text}")

        elif field_name == "agents_used":
            # Agents are strings in the array
            agent = str(item).strip('"')
            if not agent or agent in self.agents_list:
                return

            self.agents_list.append(agent)
            if self.agents_container:
                agents_text = ", ".join(self.agents_list)
                self.agents_container.markdown(f"**Agents Used:** {agents_text}")
