from ..gui.components.bridge_data.main import BRIDGE_FIELDS
from ..gui.project_controller import ProjectController
from .common_code import fields_to_latex


CHUNK = "bridge_data"


def bridge_data_to_latex(controller: ProjectController) -> str:
    data = controller.get_chunk(CHUNK)
    return fields_to_latex(BRIDGE_FIELDS, data, "Bridge Data Summary", "tab:bridge_data")
