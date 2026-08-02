import { app } from "../../scripts/app.js";

function currentSeedValue(output) {
  const value = output?.current_seed;
  if (Array.isArray(value)) {
    return value.length ? String(value[0]) : null;
  }
  if (value === undefined || value === null) {
    return null;
  }
  return String(value);
}

function configureCurrentSeedWidget(node) {
  const widget = node.widgets?.find((item) => item.name === "current_seed");
  if (!widget) {
    return;
  }
  widget.options ||= {};
  widget.options.read_only = true;
}

app.registerExtension({
  name: "Xiawan.GlobalSeedManagerCurrentSeed",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "XiawanGlobalSeedManager") {
      return;
    }

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onNodeCreated?.apply(this, arguments);
      configureCurrentSeedWidget(this);
      return result;
    };

    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const result = onConfigure?.apply(this, arguments);
      configureCurrentSeedWidget(this);
      return result;
    };

    const onExecuted = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (output) {
      const result = onExecuted?.apply(this, arguments);
      const seed = currentSeedValue(output);
      const widget = this.widgets?.find((item) => item.name === "current_seed");
      if (seed !== null && widget) {
        widget.value = seed;
        this.graph?.setDirtyCanvas(true, false);
      }
      return result;
    };
  },
});
