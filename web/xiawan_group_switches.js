import { app } from "../../scripts/app.js";

// A Xiawan-owned recreation of the compact group controls used in the Alice
// workflow. It draws directly on the LiteGraph canvas so it remains reliable
// for output nodes without backend-declared widgets.
const MANAGER_TYPES = new Set(["GroupIgnoreManager", "GroupMuteManager"]);
const TITLE_HEIGHT = 30;
const PANEL_TOP = TITLE_HEIGHT + 7;
const PANEL_BOTTOM = 8;
const PANEL_LEFT = 12;
const PANEL_RIGHT = 12;
const NAVIGATION_WIDTH = 31;
const REFINE_LOGICAL_MASTER = "逻辑-4 部位细化";
const REFINE_PANEL_PROXY = "__xw_refine_panel_proxy__";
const FALLBACK_LOCKED_SIZES = new Map([
  [110, [450, 280]],
  [123, [450, 280]],
  [156, [450, 220]],
]);

function managerNodes(graph) {
  return (graph?._nodes || []).filter((node) => MANAGER_TYPES.has(node.type));
}

function groupEntries(node) {
  return Array.isArray(node?.properties?.groups) ? node.properties.groups : [];
}

function orderedEntries(node) {
  const entries = groupEntries(node);
  const byName = new Map(entries.map((entry) => [entry.group_name, entry]));
  const ordered = (node.properties?.customGroupOrder || [])
    .map((name) => byName.get(name))
    .filter(Boolean);

  for (const entry of entries) {
    if (!ordered.includes(entry)) {
      ordered.push(entry);
    }
  }

  // Older Group Ignore Manager clients omit the first configured row of a
  // secondary panel. Render a small proxy for the shared refine master so the
  // user always has a visible total switch. Its state and click target remain
  // the canonical main-chain "4 refine" group.
  if (
    Number(node?.id) === 156 &&
    !ordered.some((entry) => entry.display_name === "总开关")
  ) {
    const masterEntries = findManagedGroups(node.graph, REFINE_LOGICAL_MASTER);
    ordered.unshift({
      group_name: REFINE_PANEL_PROXY,
      display_name: "总开关",
      enabled: masterEntries.some(({ entry }) => Boolean(entry.enabled)),
      xiawanProxyTarget: REFINE_LOGICAL_MASTER,
    });
  }
  return ordered;
}

function lockedPanelSize(node) {
  const size = node?.properties?.xiawan_switch_locked_size || FALLBACK_LOCKED_SIZES.get(Number(node?.id));
  if (
    Array.isArray(size) &&
    size.length === 2 &&
    Number.isFinite(size[0]) &&
    Number.isFinite(size[1])
  ) {
    return size;
  }
  return node.size;
}

function enforceLockedPanelGeometry(node) {
  const lockedSize = lockedPanelSize(node);
  if (!lockedSize || node.size[0] === lockedSize[0] && node.size[1] === lockedSize[1]) {
    return;
  }
  node.setSize?.([...lockedSize]);
  node.size[0] = lockedSize[0];
  node.size[1] = lockedSize[1];
  node.graph?.setDirtyCanvas?.(true, true);
}

function findManagedGroups(graph, groupName) {
  const matches = [];
  for (const node of managerNodes(graph)) {
    for (const entry of groupEntries(node)) {
      if (entry.group_name === groupName) {
        matches.push({ node, entry });
      }
    }
  }
  return matches;
}

function refreshStateCaches(graph) {
  const states = {};
  for (const node of managerNodes(graph)) {
    for (const entry of groupEntries(node)) {
      if (entry?.group_name) {
        states[entry.group_name] = Boolean(entry.enabled);
      }
    }
  }

  for (const node of managerNodes(graph)) {
    node.properties ||= {};
    node.properties.groupStatesCache = { ...states };
  }
}

function setManagedGroupEnabled(graph, groupName, enabled, visited = new Set()) {
  if (visited.has(groupName)) {
    return;
  }
  visited.add(groupName);

  const managedEntries = findManagedGroups(graph, groupName);
  if (!managedEntries.length) {
    return;
  }

  const actions = [];
  for (const { entry } of managedEntries) {
    entry.enabled = Boolean(enabled);
    actions.push(
      ...(entry.enabled ? entry.linkage?.on_enable || [] : entry.linkage?.on_disable || []),
    );
  }

  for (const action of actions) {
    if (!action?.target_group) {
      continue;
    }
    if (action.action === "enable") {
      setManagedGroupEnabled(graph, action.target_group, true, visited);
    } else if (action.action === "disable") {
      setManagedGroupEnabled(graph, action.target_group, false, visited);
    }
  }
}

function isMainPanelMaster(node, entry) {
  return (
    Number(node?.id) === 110 &&
    entry?.xiawanMainPanelMaster === true
  );
}

function isRefinePanelMaster(node, entry) {
  return (
    Number(node?.id) === 156 &&
    entry?.xiawanRefinePanelMaster === true
  );
}

function effectiveEntryEnabled(node, entry) {
  if (entry?.xiawanProxyTarget) {
    return findManagedGroups(node.graph, entry.xiawanProxyTarget)
      .some(({ entry: target }) => Boolean(target.enabled));
  }

  if (isMainPanelMaster(node, entry)) {
    return Boolean(entry.enabled) || managerNodes(node.graph).some((owner) =>
      groupEntries(owner).some((candidate) =>
        candidate.group_name !== entry.group_name && Boolean(candidate.enabled),
      ),
    );
  }

  if (isRefinePanelMaster(node, entry)) {
    return findManagedGroups(node.graph, REFINE_LOGICAL_MASTER)
      .some(({ entry: target }) => Boolean(target.enabled));
  }

  return Boolean(entry?.enabled);
}

function rowGeometry(node, entries) {
  if (!entries.length) {
    return { height: 0, start: PANEL_TOP };
  }
  return {
    start: PANEL_TOP,
    height: Math.max(22, (lockedPanelSize(node)[1] - PANEL_TOP - PANEL_BOTTOM) / entries.length),
  };
}

function roundedRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width * 0.5, height * 0.5);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function functionalColor(entry) {
  const name = `${entry.group_name || ""} ${entry.display_name || ""}`.toLowerCase();
  if (name.includes("sdxl") || name.includes("anima") || name.includes("底图")) return "#6ca8c8";
  if (name.includes("openpose") || name.includes("scribble") || name.includes("lineart") || name.includes("depth")) return "#76ad91";
  if (name.includes("图像反推") || name.includes("画廊")) return "#c99268";
  if (name.includes("潜放") || name.includes("迭代") || name.includes("放大")) return "#9a83be";
  if (name.includes("细化") || name.includes("脸") || name.includes("眼") || name.includes("手") || name.includes("足")) return "#bd8299";
  return "#91a8bd";
}

function fitText(ctx, value, maxWidth) {
  const text = String(value || "");
  if (ctx.measureText(text).width <= maxWidth) {
    return text;
  }
  let end = text.length;
  while (end > 1 && ctx.measureText(`${text.slice(0, end)}...`).width > maxWidth) {
    end -= 1;
  }
  return `${text.slice(0, end)}...`;
}

function drawPanel(node, ctx) {
  const entries = orderedEntries(node);
  const { start, height } = rowGeometry(node, entries);
  const width = lockedPanelSize(node)[0];

  ctx.save();
  ctx.font = "13px Arial";
  ctx.textBaseline = "middle";
  for (const [index, entry] of entries.entries()) {
    const y = start + index * height;
    const rowHeight = Math.max(20, height - 3);
    const active = effectiveEntryEnabled(node, entry);
    const color = functionalColor(entry);

    ctx.fillStyle = active ? "#273238" : "#202428";
    roundedRect(ctx, PANEL_LEFT, y, width - PANEL_LEFT - PANEL_RIGHT, rowHeight, 5);
    ctx.fill();

    ctx.fillStyle = color;
    roundedRect(ctx, PANEL_LEFT, y, 5, rowHeight, 3);
    ctx.fill();

    const pillWidth = 54;
    const pillHeight = Math.min(18, rowHeight - 6);
    const pillX = width - PANEL_RIGHT - NAVIGATION_WIDTH - pillWidth - 8;
    const pillY = y + (rowHeight - pillHeight) * 0.5;
    ctx.fillStyle = active ? "#5ea78a" : "#3c454c";
    roundedRect(ctx, pillX, pillY, pillWidth, pillHeight, pillHeight * 0.5);
    ctx.fill();

    const knobRadius = Math.max(4, pillHeight * 0.36);
    ctx.fillStyle = active ? "#e6f4e9" : "#aeb8bd";
    ctx.beginPath();
    ctx.arc(active ? pillX + pillWidth - knobRadius - 4 : pillX + knobRadius + 4, y + rowHeight * 0.5, knobRadius, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = active ? "#eaf4ee" : "#b7c0c5";
    ctx.textAlign = "left";
    const label = entry.display_name || entry.group_name;
    const labelWidth = pillX - PANEL_LEFT - 16;
    ctx.fillText(fitText(ctx, label, labelWidth), PANEL_LEFT + 13, y + rowHeight * 0.5 + 0.5);

    const navX = width - PANEL_RIGHT - NAVIGATION_WIDTH;
    ctx.strokeStyle = "#8fa4ad";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(navX, y + 5);
    ctx.lineTo(navX, y + rowHeight - 5);
    ctx.stroke();
    ctx.fillStyle = "#8fa4ad";
    ctx.beginPath();
    ctx.moveTo(navX + 10, y + rowHeight * 0.5);
    ctx.lineTo(navX + 18, y + rowHeight * 0.5 - 5);
    ctx.lineTo(navX + 18, y + rowHeight * 0.5 + 5);
    ctx.closePath();
    ctx.fill();
  }
  ctx.restore();
}

function navigateToGroup(node, groupName) {
  const canvas = app.canvas;
  const group = node.graph?._groups?.find((item) => item.title === groupName);
  if (!canvas || !group) {
    return;
  }
  canvas.centerOnNode?.(group);
  canvas.setDirty?.(true, true);
}

function installPanel(node) {
  if (!node || node.__xwGroupSwitchPanelInstalled) {
    return;
  }
  node.__xwGroupSwitchPanelInstalled = true;

  const originalComputeSize = node.computeSize;
  node.computeSize = function (out) {
    const lockedSize = lockedPanelSize(this);
    if (!lockedSize) {
      return originalComputeSize?.apply(this, arguments);
    }
    if (out) {
      out[0] = lockedSize[0];
      out[1] = lockedSize[1];
      return out;
    }
    return [...lockedSize];
  };

  const originalDrawForeground = node.onDrawForeground;
  node.onDrawForeground = function (ctx) {
    enforceLockedPanelGeometry(this);
    originalDrawForeground?.apply(this, arguments);
    drawPanel(this, ctx);
  };

  const originalMouseDown = node.onMouseDown;
  node.onMouseDown = function (event, position) {
    const entries = orderedEntries(this);
    const { start, height } = rowGeometry(this, entries);
    const localY = position?.[1];
    const localX = position?.[0];
    const index = Number.isFinite(localY) ? Math.floor((localY - start) / height) : -1;
    if (index >= 0 && index < entries.length && localY >= start) {
      const entry = entries[index];
      const targetGroup = entry.xiawanProxyTarget || entry.group_name;
      if (localX >= this.size[0] - PANEL_RIGHT - NAVIGATION_WIDTH) {
        navigateToGroup(this, targetGroup);
      } else {
        const nextEnabled = !effectiveEntryEnabled(this, entry);
        // Keep the master row itself coherent even on GroupIgnoreManager
        // builds that only propagate its linkage actions to child rows.
        if (!entry.xiawanProxyTarget) {
          entry.enabled = nextEnabled;
        }
        setManagedGroupEnabled(this.graph, targetGroup, nextEnabled);
        refreshStateCaches(this.graph);
        this.graph?.setDirtyCanvas?.(true, false);
      }
      return true;
    }
    return originalMouseDown?.apply(this, arguments);
  };
}

app.registerExtension({
  name: "XW.GroupSwitchPanel",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (!MANAGER_TYPES.has(nodeData.name)) {
      return;
    }

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated?.apply(this, arguments);
      installPanel(this);
      enforceLockedPanelGeometry(this);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure?.apply(this, arguments);
      installPanel(this);
      enforceLockedPanelGeometry(this);
      this.graph?.setDirtyCanvas?.(true, false);
      return result;
    };
  },

  loadedGraphNode(node) {
    if (MANAGER_TYPES.has(node?.type)) {
      installPanel(node);
      const enforce = () => {
        enforceLockedPanelGeometry(node);
        node.graph?.setDirtyCanvas?.(true, false);
      };
      requestAnimationFrame(enforce);
      setTimeout(enforce, 0);
      setTimeout(enforce, 100);
    }
  },
});
