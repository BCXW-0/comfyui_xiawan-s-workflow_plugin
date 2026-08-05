"""Build the R-1.4.0 clean template from the R-1.3.0 template.

The developer workflow is intentionally not read by this migration. Existing
node geometry is preserved; only the branch links required by the new
compatibility switches are redirected or added to the published template.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "workflows" / "Xiawan's Workflow ver.R-1.3.0.json"
DESTINATION = ROOT / "workflows" / "Xiawan's Workflow ver.R-1.4.0.json"
def _node_map(workflow):
    return {int(node["id"]): node for node in workflow["nodes"]}


def _set_output_links(node, slot, links):
    node["outputs"][slot]["links"] = list(links)


def _append_output_link(node, slot, link_id):
    links = node["outputs"][slot].get("links") or []
    if link_id not in links:
        links.append(link_id)
    node["outputs"][slot]["links"] = links


def _new_switch(base_node, node_id, node_type, title, position, inputs, outputs, order):
    node = deepcopy(base_node)
    node.update(
        {
            "id": node_id,
            "type": node_type,
            "pos": list(position),
            "size": [300, 98],
            "order": order,
            "inputs": inputs,
            "outputs": outputs,
            "title": title,
            "widgets_values": [],
            "properties": {
                "Node name for S&R": node_type,
                "xiawan_layer": "hidden_logic",
                "xiawan_visibility": "hidden",
                "collapsed": True,
                "xiawan_size_locked": True,
                "xiawan_func": "logic",
                "xiawan_position_locked": True,
                "xiawan_layout_locked": True,
            },
        }
    )
    return node


def build():
    workflow = json.loads(SOURCE.read_text(encoding="utf-8"))
    nodes = _node_map(workflow)
    links = {int(link[0]): link for link in workflow["links"]}

    # The existing SDXL VAE link becomes the false branch of the shared VAE switch.
    links[18][3] = 333
    links[18][4] = 1
    nodes[66]["inputs"][1]["link"] = 961
    nodes[258]["outputs"][2]["links"] = [542, 555, 962]
    nodes[257]["outputs"][2]["links"] = [588, 589, 963, 966]
    _append_output_link(nodes[287], 4, 966)
    _append_output_link(nodes[318], 0, 965)

    # Anima image-to-image uses the same prepared pixels as SDXL, encoded by the
    # selected branch VAE, then chooses empty or encoded latent by I2I mode.
    links[534][3] = 334
    links[534][4] = 1
    nodes[266]["outputs"][0]["links"] = [534]
    nodes[267]["inputs"][3]["link"] = 964

    switch_base = nodes[318]
    vae_switch = _new_switch(
        switch_base,
        333,
        "XiawanVAESwitch",
        "I2I VAE · SDXL/Anima",
        (-760, -700),
        [
            {"localized_name": "Anima 分支", "name": "switch", "type": "BOOLEAN", "link": 963},
            {"localized_name": "SDXL VAE", "name": "on_false", "shape": 7, "type": "VAE", "link": 18},
            {"localized_name": "Anima VAE", "name": "on_true", "shape": 7, "type": "VAE", "link": 962},
        ],
        [{"localized_name": "VAE", "name": "vae", "type": "VAE", "slot_index": 0, "links": [961]}],
        224,
    )
    latent_switch = _new_switch(
        switch_base,
        334,
        "XiawanLatentSwitch",
        "Anima I2I latent",
        (420, 3890),
        [
            {"localized_name": "图生图模式", "name": "switch", "type": "BOOLEAN", "link": 966},
            {"localized_name": "Anima 空 latent", "name": "on_false", "shape": 7, "type": "LATENT", "link": 534},
            {"localized_name": "Anima 图生图 latent", "name": "on_true", "shape": 7, "type": "LATENT", "link": 965},
        ],
        [{"localized_name": "latent", "name": "latent", "type": "LATENT", "slot_index": 0, "links": [964]}],
        225,
    )
    workflow["nodes"].extend([vae_switch, latent_switch])

    workflow["links"].extend(
        [
            [961, 333, 0, 66, 1, "VAE"],
            [962, 258, 2, 333, 2, "VAE"],
            [963, 257, 2, 333, 0, "BOOLEAN"],
            [964, 334, 0, 267, 3, "LATENT"],
            [965, 318, 0, 334, 2, "LATENT"],
            [966, 287, 4, 334, 0, "BOOLEAN"],
        ]
    )

    nodes[255]["widgets_values"][3:7] = [30, 4, 1, "er_sde"]
    workflow["last_node_id"] = 334
    workflow["last_link_id"] = 966

    extra = workflow.setdefault("extra", {})
    extra["frontendVersion"] = "1.45.21"
    extra["xiawan_release_version"] = "R-1.4.0"
    xiawan = extra.setdefault("xiawan", {})
    xiawan["release_version"] = "R-1.4.0"
    xiawan["layout_audit"] = {
        "nodes": len(workflow["nodes"]),
        "links": len(workflow["links"]),
        "groups": len(workflow.get("groups", [])),
        "last_link_id": workflow["last_link_id"],
        "positions_and_sizes_changed": False,
        "new_nodes": [333, 334],
    }
    if isinstance(xiawan.get("both_reflow"), dict):
        xiawan["both_reflow"]["links"] = len(workflow["links"])
    xiawan["anima_compatibility"] = {
        "native_runtime": "ComfyUI 0.28.0 or newer",
        "llm_adapter": "native",
        "i2i_vae_switch_node": 333,
        "i2i_latent_switch_node": 334,
        "defaults": {"steps": 30, "cfg": 4.0, "sampler": "er_sde", "scheduler": "simple"},
    }

    DESTINATION.write_text(
        json.dumps(workflow, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
