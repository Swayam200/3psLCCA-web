from .manager import StructureManagerWidget


class FoundationWidget(StructureManagerWidget):
    def __init__(self, controller):
        # Explicitly call the parent Manager's __init__
        StructureManagerWidget.__init__(
            self,
            controller=controller,
            chunk_name="str_foundation",
        )


