from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R11 = ROOT / "workflows" / "Xiawan's Workflow ver.R-1.1.json"
R12 = ROOT / "workflows" / "Xiawan's Workflow ver.R-1.2.0.json"
SEED_LINK_IDS = {92, 105, 117, 182, 323, 324, 325, 336, 344, 433, 535, 674}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def nodes_by_id(workflow):
    return {int(node["id"]): node for node in workflow["nodes"]}


def test_release_structure_is_valid():
    workflow = load(R12)
    nodes = nodes_by_id(workflow)
    node_ids = list(nodes)
    link_ids = [int(link[0]) for link in workflow["links"]]
    assert len(node_ids) == len(set(node_ids))
    assert len(link_ids) == len(set(link_ids))
    assert workflow["last_link_id"] == max(link_ids)

    links = {int(link[0]): link for link in workflow["links"]}
    for link_id, link in links.items():
        source = nodes[link[1]]
        target = nodes[link[3]]
        assert link[2] < len(source.get("outputs", [])), link_id
        assert link[4] < len(target.get("inputs", [])), link_id
        assert link_id in (source["outputs"][link[2]].get("links") or [])
        assert target["inputs"][link[4]]["link"] == link_id

    for node in workflow["nodes"]:
        for output in node.get("outputs", []):
            for link_id in output.get("links") or []:
                assert int(link_id) in links
        for input_slot in node.get("inputs", []):
            if input_slot.get("link") is not None:
                assert int(input_slot["link"]) in links


def test_release_preserves_geometry():
    before = nodes_by_id(load(R11))
    after = nodes_by_id(load(R12))
    assert set(before) == set(after)
    for node_id in before:
        assert before[node_id].get("pos") == after[node_id].get("pos")
        assert before[node_id].get("size") == after[node_id].get("size")


def test_seed_matrix_reaches_sampling_links():
    workflow = load(R12)
    links = {int(link[0]): link for link in workflow["links"]}
    assert {links[link_id][1] for link_id in SEED_LINK_IDS} == {292}
    assert {links[link_id][2] for link_id in SEED_LINK_IDS} == {0}


def test_release_is_a_clean_template():
    nodes = nodes_by_id(load(R12))
    assert nodes[8]["widgets_values"][0] == ""
    assert nodes[9]["widgets_values"][0] == ""
    assert nodes[10]["widgets_values"][1] == ""
    assert nodes[261]["widgets_values"][1] == ""
    assert nodes[42]["widgets_values"][0] == "example.png"
    assert nodes[46]["widgets_values"][0] == "example.png"
    assert nodes[126]["widgets_values"][0] == ""
    assert nodes[127]["widgets_values"][0] == ""
    assert nodes[129]["widgets_values"][0] == ""
    assert nodes[130]["widgets_values"][0] == ""
    assert nodes[292]["widgets_values"][4] is False
    assert nodes[308]["widgets_values"][0] == ""
    assert nodes[308]["widgets_values"][1] == ""
    assert nodes[308]["widgets_values"][5] == ""
    assert nodes[308]["widgets_values"][6] == ""
    assert nodes[308]["properties"]["xiawan_func"] == "output"
