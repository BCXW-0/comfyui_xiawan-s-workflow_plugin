(function installIntelligentTagImport() {
  if (window.xiawanIntelligentTagImportInstalled) return;
  window.xiawanIntelligentTagImportInstalled = true;

  const endpoint = '/weilin/prompt_ui/api/prompt/intelligent_tag_import';
  const buttonId = 'xiawan-intelligent-tag-import-button';
  const inputId = 'xiawan-intelligent-tag-import-input';

  const showStatus = (host, message, isError) => {
    let status = host.querySelector('[data-xiawan-tag-import-status]');
    if (!status) {
      status = document.createElement('span');
      status.dataset.xiawanTagImportStatus = 'true';
      status.style.cssText = 'margin-left:10px;font-size:12px;vertical-align:middle;';
      host.appendChild(status);
    }
    status.textContent = message;
    status.style.color = isError ? '#ff8a80' : '#8bc34a';
  };

  const importFile = async (file, button, host) => {
    button.disabled = true;
    button.textContent = '分析中...';
    const form = new FormData();
    form.append('file', file, file.name);
    try {
      const response = await fetch(endpoint, { method: 'POST', body: form });
      const payload = await response.json();
      if (!response.ok || payload.code !== 200) {
        throw new Error(payload.message || '导入失败');
      }
      const data = payload.data || {};
      const newTags = data.new_tags ?? data.tags ?? 0;
      const skippedDuplicates = data.skipped_duplicates ?? 0;
      window.postMessage({ type: 'weilin_prompt_ui_tag_manager_refresh' }, '*');
      showStatus(
        host,
        `导入成功，新增 ${newTags} 个 Tag，跳过 ${skippedDuplicates} 个重复项。标签管理面板已自动刷新（${data.groups || 0} 个一级分类、${data.subgroups || 0} 个二级分类）`,
        false,
      );
      window.setTimeout(() => {
        window.alert('导入成功，标签管理面板已自动刷新，请返回标签管理面板查看。');
      }, 0);
    } catch (error) {
      console.error('[Xiawan] Intelligent tag import failed:', error);
      showStatus(host, error.message || '导入失败', true);
    } finally {
      button.disabled = false;
      button.textContent = '智能法典分析';
    }
  };

  const installButton = () => {
    const sqlInput = document.querySelector('input[type="file"][accept=".sql"]');
    if (!sqlInput || document.getElementById(buttonId)) return;
    const host = sqlInput.parentElement;
    if (!host) return;

    const input = document.createElement('input');
    input.id = inputId;
    input.type = 'file';
    input.accept = '.txt,.doc,.docx';
    input.style.display = 'none';

    const button = document.createElement('button');
    button.id = buttonId;
    button.type = 'button';
    button.textContent = '智能法典分析';
    button.style.marginLeft = '10px';
    button.title = '从 TXT、DOC 或 DOCX 识别分类、Tag 和描述并导入';
    button.addEventListener('click', () => input.click());
    input.addEventListener('change', () => {
      const file = input.files && input.files[0];
      input.value = '';
      if (file) importFile(file, button, host);
    });

    host.appendChild(input);
    host.appendChild(button);
  };

  const observer = new MutationObserver(installButton);
  const start = () => {
    installButton();
    observer.observe(document.body, { childList: true, subtree: true });
  };
  if (document.body) start();
  else window.addEventListener('DOMContentLoaded', start, { once: true });
})();
