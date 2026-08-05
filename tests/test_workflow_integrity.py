from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
R122 = ROOT / "workflows" / "Xiawan's Workflow ver.R-1.2.2.json"
R123 = ROOT / "workflows" / "Xiawan's Workflow ver.R-1.2.3.json"
R130 = ROOT / "workflows" / "Xiawan's Workflow ver.R-1.3.0.json"
R140 = ROOT / "workflows" / "Xiawan's Workflow ver.R-1.4.0.json"
SEED_LINK_IDS = {92, 105, 117, 182, 323, 324, 325, 336, 344, 433, 535, 674}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def nodes_by_id(workflow):
    return {int(node["id"]): node for node in workflow["nodes"]}


def test_release_structure_is_valid():
    workflow = load(R140)
    nodes = nodes_by_id(workflow)
    node_ids = list(nodes)
    link_ids = [int(link[0]) for link in workflow["links"]]
    assert len(node_ids) == 226
    assert len(link_ids) == 569
    assert len(workflow["groups"]) == 35
    assert len(node_ids) == len(set(node_ids))
    assert len(link_ids) == len(set(link_ids))
    assert workflow["last_link_id"] == max(link_ids)
    assert workflow["last_node_id"] == max(node_ids)

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
    before = nodes_by_id(load(R130))
    after = nodes_by_id(load(R140))
    assert set(before) <= set(after)
    for node_id in before:
        assert before[node_id].get("pos") == after[node_id].get("pos")
        assert before[node_id].get("size") == after[node_id].get("size")


def test_release_nodes_do_not_overlap():
    workflow = load(R140)
    boxes = []
    for node in workflow["nodes"]:
        x, y = node["pos"]
        width, height = node["size"]
        boxes.append((int(node["id"]), x, y, x + width, y + height))

    for index, left in enumerate(boxes):
        for right in boxes[index + 1 :]:
            assert not (
                left[1] < right[3]
                and right[1] < left[3]
                and left[2] < right[4]
                and right[2] < left[4]
            ), (left[0], right[0])


def test_seed_matrix_reaches_sampling_links():
    workflow = load(R140)
    links = {int(link[0]): link for link in workflow["links"]}
    assert {links[link_id][1] for link_id in SEED_LINK_IDS} == {292}
    assert {links[link_id][2] for link_id in SEED_LINK_IDS} == {0}


def test_anima_chain_uses_native_branch_vae_and_i2i_latent():
    workflow = load(R140)
    nodes = nodes_by_id(workflow)
    links = {int(link[0]): link for link in workflow["links"]}

    assert nodes[333]["type"] == "XiawanVAESwitch"
    assert nodes[334]["type"] == "XiawanLatentSwitch"
    assert links[18][1:5] == [8, 2, 333, 1]
    assert links[961][1:5] == [333, 0, 66, 1]
    assert links[962][1:5] == [258, 2, 333, 2]
    assert links[963][1:5] == [257, 2, 333, 0]
    assert links[534][1:5] == [266, 0, 334, 1]
    assert links[964][1:5] == [334, 0, 267, 3]
    assert links[965][1:5] == [318, 0, 334, 2]
    assert links[966][1:5] == [287, 4, 334, 0]
    assert nodes[66]["inputs"][1]["link"] == 961
    assert nodes[267]["inputs"][3]["link"] == 964
    assert nodes[257]["outputs"][2]["links"] == [588, 589, 963, 966]


def test_anima_defaults_match_native_baseline():
    nodes = nodes_by_id(load(R140))
    assert nodes[255]["widgets_values"] == [832, 1216, 1, 30, 4, 1, "er_sde", "simple"]


def test_release_is_a_clean_template():
    nodes = nodes_by_id(load(R140))
    assert nodes[8]["widgets_values"][0] == ""
    assert nodes[9]["widgets_values"][0] == ""
    assert nodes[10]["widgets_values"][1] == ""
    assert nodes[258]["widgets_values"][:3] == ["", "", ""]
    assert nodes[261]["widgets_values"][1] == ""
    assert all(node["widgets_values"][0] == "example.png" for node in nodes.values() if node["type"] == "LoadImage")
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


def test_release_metadata_is_current():
    workflow = load(R140)
    assert workflow["extra"]["frontendVersion"] == "1.45.21"
    assert workflow["extra"]["xiawan"]["release_version"] == "R-1.4.0"
    assert workflow["extra"]["xiawan_release_version"] == "R-1.4.0"
    assert workflow["extra"]["xiawan"]["layout_audit"]["links"] == 569
