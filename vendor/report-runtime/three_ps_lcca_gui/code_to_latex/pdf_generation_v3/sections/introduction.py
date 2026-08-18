from ..latex_helpers import paragraph, section


def _framework_figure() -> str:
    image_path = "../pdf_generation_v3/images/image_1.png"

    return "\n".join([
        r"\begin{figure}[H]",
        r"\centering",
        r"\includegraphics[width=0.82\textwidth]{" + image_path + r"}",
        r"\caption{3PS-LCC framework}",
        r"\end{figure}",
    ])


def introduction_to_latex() -> str:
    return "\n\n".join([
        section("Introduction to Life Cycle Cost Assessment"),
        paragraph(
            "Life Cycle Cost is the total cost incurred by the bridge throughout its life. " \
            "This report presents Life Cycle Cost Assessment (LCCA) based on the Three Pillars of Sustainability-Life Cycle Cost (3PS-LCC) framework, which considers the economic, social, and environmental pillars over the selected analysis period. " \
            "The various life-cycle stages and sustainability pillars considered in the 3PS-LCC framework are illustrated in Figure 1."
        ),
        _framework_figure(),
    ])
