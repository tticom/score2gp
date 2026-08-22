class HumanReadableConversionError(Exception):
    """
    A conversion error that is formatted for a non-technical musician,
    pinpointing the location of the error in the original document.
    """
    def __init__(
        self,
        message: str,
        page: int | None = None,
        measure: int | None = None,
        staff: int | None = None,
        voice: int | None = None,
        beat: float | None = None
    ):
        self.message = message
        self.page = page
        self.measure = measure
        self.staff = staff
        self.voice = voice
        self.beat = beat
        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = []
        if self.page is not None:
            parts.append(f"Page {self.page}")
        if self.measure is not None:
            parts.append(f"Measure {self.measure}")
        if self.staff is not None:
            parts.append(f"Staff {self.staff}")
        if self.voice is not None:
            parts.append(f"Voice {self.voice}")
        if self.beat is not None:
            parts.append(f"Beat {self.beat}")

        loc = ", ".join(parts)
        if loc:
            return f"Error at {loc}: {self.message}"
        return f"Error: {self.message}"
