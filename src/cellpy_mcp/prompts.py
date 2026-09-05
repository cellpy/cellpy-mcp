"""Named starting points, for people who are not asking for tools.

Tools serve someone who already knows what they want. Someone who opens a chat
window and asks it to "do the cell processing" does not, and the gap is not
knowledge of cellpy — it is not knowing that any of this is there.

Prompts are the part of MCP that addresses exactly that: a client renders them
as named, pickable entries, so the capability advertises itself instead of
waiting to be asked for. They are also the cheapest place to put the traps that
documentation is bad at preventing, because they are the words the model starts
from.
"""

from __future__ import annotations

__all__ = ["register"]


def register(server) -> None:
    @server.prompt(title="Analyse a cell file")
    def analyse_cell(path: str, mass_mg: str = "") -> str:
        """Load one cell and produce the standard set of plots."""
        mass = (
            f"Its active-material mass is {mass_mg} mg — pass it to load_cell."
            if mass_mg.strip()
            else (
                "No mass was given. Ask for it before reporting any gravimetric "
                "number: without it cellpy computes against a default of 1.0 mg "
                "and the capacities look plausible and are wrong."
            )
        )
        return (
            f"Analyse the battery cell at {path!r}.\n\n{mass}\n\n"
            "Work in this order:\n"
            "1. load_cell, and tell me the cycle count and the mass you used.\n"
            "2. describe_plot_families, and say which are unavailable and why.\n"
            "3. collect the summary and render capacity-vs-cycle and coulombic "
            "efficiency to html files next to the data.\n"
            "4. Report what the curves do — capacity fade, any outlying cycles "
            "— in plain language, and name the files you wrote."
        )

    @server.prompt(title="Start a batch project")
    def start_batch_project(project: str = "", experiment: str = "") -> str:
        """Set up the notebook template for a new set of experiments."""
        named = (
            f"Call it {project!r}, experiment {experiment!r}."
            if project.strip() and experiment.strip()
            else "Ask me for a project name and an experiment name first."
        )
        return (
            f"Set up a new cellpy batch project. {named}\n\n"
            "Use list_templates to show me the options and say which is the "
            "default, then new_project. Afterwards, list the notebooks it made, "
            "say in one line each what they are for, and give me the single "
            "command that opens them."
        )

    @server.prompt(title="How does a cellpy call work?")
    def explain_call(name: str) -> str:
        """Explain a cellpy function: arguments, defaults, and the traps."""
        return (
            f"Explain how {name!r} works in cellpy.\n\n"
            "Use describe_api. Give me the arguments that matter with their "
            "defaults, and a short worked example. If the call has "
            "undocumented_parameters that bear on my question, read the source "
            "with include_source=True rather than guessing — and say which "
            "parts of your answer came from the source rather than the "
            "documentation."
        )
