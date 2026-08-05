"""Apply the R-1.1 compatibility migration to a Xiawan workflow JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SEED_LINK_IDS = (92, 105, 117, 182, 323, 324, 325, 336, 344, 433, 535, 674)
PROMPT_NODE_TYPES = {"PromptSelector", "WeiLinPromptUIWithoutLora"}
DETAIL_PARAM_TYPE = "XiawanSingleRegionDetailerParams"


def _node_map(workflow):
    return {int(node["id"]): node for node in workflow.get("nodes", [])}


def _output(node, slot):
    outputs = node.setdefault("outputs", [])
    while len(outputs) <= slot:
        outputs.append({"links": None})
    return outputs[slot]


def _link_map(workflow):
    return {int(link[0]): link for link in workflow.get("links", [])}


def _remove_link(output, link_id):
    links = output.get("links")
    if not isinstance(links, list):
        return
    output["links"] = [value for value in links if int(value) != link_id] or None


def _add_link(output, link_id):
    links = output.get("links")
    if not isinstance(links, list):
        links = []
    if link_id not in links:
        links.append(link_id)
    output["links"] = links


def connect_seed_matrix(workflow):
    nodes = _node_map(workflow)
    links = _link_map(workflow)
    matrix = nodes[292]
    global_seed = nodes[275]
    matrix_output = _output(matrix, 0)
    for link_id in SEED_LINK_IDS:
        link = links[link_id]
        if int(link[1]) == 275:
            _remove_link(_output(global_seed, int(link[2])), link_id)
        link[1] = 292
        link[2] = 0
        _add_link(matrix_output, link_id)


def _set_widget(node, index, value):
    values = node.setdefault("widgets_values", [])
    while len(values) <= index:
        values.append("")
    values[index] = value


def _clear_published_inputs(workflow):
    for node in workflow.get("nodes", []):
        node_type = node.get("type")
        title = str(node.get("title") or "")
        values = node.get("widgets_values")
        if node_type == "CheckpointLoaderSimpleMira":
            _set_widget(node, 0, "")
        elif node_type == "Lora Loader (LoraManager)":
            _set_widget(node, 1, "")
            _set_widget(node, 2, [])
        elif node_type == "XiawanAnimaModelLoader":
            for index in (0, 1, 2):
                _set_widget(node, index, "")
        elif node_type == "LoadImage":
            _set_widget(node, 0, "example.png")
        elif node_type in PROMPT_NODE_TYPES:
            _set_widget(node, 0, "")
            if node_type == "WeiLinPromptUIWithoutLora":
                for index, value in enumerate(values or []):
                    if not isinstance(value, bool):
                        _set_widget(node, index, "")
            if node_type == "PromptSelector":
                _set_widget(node, 1, "")
                properties = node.setdefault("properties", {})
                properties["selectedPrompts"] = "{}"
        elif node_type == "XiawanPromptAB":
            _set_widget(node, 0, "")
            _set_widget(node, 1, "")
        elif node_type == DETAIL_PARAM_TYPE:
            if values:
                _set_widget(node, len(values) - 1, "")
        elif node_type == "XiawanSaveMetaPack":
            _set_widget(node, 0, "")
            _set_widget(node, 1, "")
            _set_widget(node, 5, "")
            _set_widget(node, 6, "")

        if node_type == "Lora Loader (LoraManager)" and "Anima" in title:
            _set_widget(node, 1, "")
            _set_widget(node, 2, [])


def update_metadata(workflow, role, release_version="R-1.1"):
    links = workflow.get("links", [])
    workflow["last_link_id"] = max((int(link[0]) for link in links), default=0)
    workflow["last_node_id"] = max((int(node["id"]) for node in workflow.get("nodes", [])), default=0)
    extra = workflow.setdefault("extra", {})
    extra["xiawan_release_version"] = release_version
    extra["xiawan_workflow_role"] = role
    extra["xiawan_schema_version"] = "1.1"
    extra["xiawan_geometry_policy"] = "existing node positions and sizes preserved"
    xiawan = extra.setdefault("xiawan", {})
    xiawan["release_version"] = release_version
    xiawan["source_of_truth"] = "published-template" if role == "published-template" else "developer-runtime"
    xiawan["layout_audit"] = {
        "nodes": len(workflow.get("nodes", [])),
        "links": len(links),
        "groups": len(workflow.get("groups", [])),
        "last_link_id": workflow["last_link_id"],
        "positions_and_sizes_changed": False,
    }
    both_reflow = xiawan.get("both_reflow")
    if isinstance(both_reflow, dict):
        both_reflow["links"] = len(links)


def migrate(source: Path, destination: Path, role: str, sanitize: bool, release_version: str = "R-1.1"):
    workflow = json.loads(source.read_text(encoding="utf-8"))
    before_geometry = {
        int(node["id"]): (node.get("pos"), node.get("size"))
        for node in workflow.get("nodes", [])
    }
    connect_seed_matrix(workflow)
    if sanitize:
        _clear_published_inputs(workflow)
    update_metadata(workflow, role, release_version)
    after_geometry = {
        int(node["id"]): (node.get("pos"), node.get("size"))
        for node in workflow.get("nodes", [])
    }
    if before_geometry != after_geometry:
        raise RuntimeError("workflow geometry changed during migration")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(workflow, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--role", choices=("published-template", "developer-runtime"), required=True)
    parser.add_argument("--sanitize", action="store_true")
    parser.add_argument("--release-version", default="R-1.1")
    args = parser.parse_args()
    migrate(args.source, args.destination, args.role, args.sanitize, args.release_version)


if __name__ == "__main__":
    main()
