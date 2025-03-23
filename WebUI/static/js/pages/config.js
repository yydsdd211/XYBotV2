let isSaving = false;

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function () {
    // 加载配置schema和配置数据
    loadConfigSchemas();

    // 创建节流版本的保存函数，500毫秒内只能触发一次
    const throttledSave = throttle(function () {
        // 如果已经在保存中，直接返回
        if (isSaving) {
            showNotification('正在保存，请稍候...', 'warning');
            return;
        }

        // 设置保存状态
        isSaving = true;

        // 立即禁用按钮，防止多次点击
        this.disabled = true;

        // 执行保存操作
        saveAllConfigs();
    }, 500);

    // 绑定保存按钮事件
    const saveButton = document.getElementById('saveConfig');
    if (saveButton) {
        saveButton.addEventListener('click', throttledSave);
    }

    // 绑定动态添加的元素事件
    document.addEventListener('click', function (e) {
        // 处理添加数组项按钮点击
        if (e.target.closest('.add-array-item')) {
            const button = e.target.closest('.add-array-item');
            const fieldId = button.dataset.fieldId;
            const configName = button.dataset.config;
            const propPath = button.dataset.path;
            handleAddArrayItem(fieldId, configName, propPath);
        }

        // 处理删除数组项按钮点击
        if (e.target.closest('.remove-array-item')) {
            const button = e.target.closest('.remove-array-item');
            button.closest('.array-item').remove();
        }

        // 处理配置折叠按钮点击
        if (e.target.closest('.config-header')) {
            const header = e.target.closest('.config-header');
            const icon = header.querySelector('i');
            icon.classList.toggle('fa-chevron-down');
            icon.classList.toggle('fa-chevron-up');
        }
    });
});

// 加载配置schema
async function loadConfigSchemas() {
    try {
        const response = await fetch('/config/api/schemas');
        const data = await response.json();

        if (data.code === 0 && data.data) {
            const schemas = data.data;
            const schemaKeys = Object.keys(schemas);

            if (schemaKeys.length === 0) {
                console.warn("Schema数据为空对象");
                document.getElementById('configSections').innerHTML = '<div class="alert alert-warning">没有可用的配置schema</div>';
                return;
            }

            // 加载配置数据
            await loadConfigs(schemas);
        } else {
            throw new Error(data.msg || '加载配置schema失败');
        }
    } catch (error) {
        console.error('加载配置schema失败:', error);
        document.getElementById('configSections').innerHTML = `<div class="alert alert-danger">加载配置schema失败: ${error.message}</div>`;
    }
}

// 加载配置数据
async function loadConfigs(schemas) {
    try {
        const response = await fetch('/config/api/config');
        const data = await response.json();

        if (data.code === 0 && data.data) {
            renderConfigForm(schemas, data.data);
        } else {
            throw new Error(data.msg || '加载配置数据失败');
        }
    } catch (error) {
        console.error('加载配置数据失败:', error);
        document.getElementById('configSections').innerHTML = `<div class="alert alert-danger">加载配置数据失败: ${error.message}</div>`;
    }
}

// 渲染配置表单
function renderConfigForm(schemas, configs) {
    const configSections = document.getElementById('configSections');
    configSections.innerHTML = '';

    for (const configName in schemas) {
        const schema = schemas[configName];
        const config = configs[configName] || {};

        const section = document.createElement('div');
        section.className = 'config-section';
        section.dataset.config = configName;

        section.innerHTML = `
            <div class="config-header" data-toggle="collapse" data-target="#config-${configName}">
                <h5>${schema.title || configName}</h5>
                <i class="fas fa-chevron-down"></i>
            </div>
            <div class="config-body collapse show" id="config-${configName}">
                <div class="config-description mb-3">
                    ${schema.description ? `<p class="text-muted">${schema.description}</p>` : ''}
                </div>
                <div class="config-fields">
                    ${renderSchemaProperties(schema, config, configName)}
                </div>
            </div>
        `;

        configSections.appendChild(section);
    }
}

// 渲染schema属性
function renderSchemaProperties(schema, config, configName, parentPath = '') {
    let html = '';

    if (schema.properties) {
        for (const propName in schema.properties) {
            const propSchema = schema.properties[propName];
            const propValue = config[propName];
            const propPath = parentPath ? `${parentPath}.${propName}` : propName;

            html += renderPropertyField(propName, propSchema, propValue, configName, propPath);
        }
    }

    return html;
}

// 渲染属性字段
function renderPropertyField(propName, propSchema, propValue, configName, propPath) {
    const fieldId = `${configName}-${propPath.replace(/\./g, '-')}`;
    const fieldName = `${configName}[${propPath}]`;
    const required = propSchema.required && propSchema.required.includes(propName);

    let fieldHtml = `
        <div class="config-field" data-path="${propPath}">
            <label for="${fieldId}">${propSchema.title || propName}${required ? ' <span class="text-danger">*</span>' : ''}</label>
    `;

    switch (propSchema.type) {
        case 'string':
            if (propSchema.enum) {
                fieldHtml += renderEnumField(fieldId, fieldName, propSchema, propValue, required);
            } else if (propSchema.format === 'password') {
                fieldHtml += renderPasswordField(fieldId, fieldName, propValue, required);
            } else if (propSchema.format === 'textarea') {
                fieldHtml += renderTextareaField(fieldId, fieldName, propValue, required);
            } else {
                fieldHtml += renderTextField(fieldId, fieldName, propValue, required);
            }
            break;

        case 'number':
        case 'integer':
            fieldHtml += renderNumberField(fieldId, fieldName, propSchema, propValue, required);
            break;

        case 'boolean':
            fieldHtml += renderBooleanField(fieldId, fieldName, propValue);
            break;

        case 'array':
            fieldHtml += renderArrayField(fieldId, propSchema, propValue || [], configName, propPath);
            break;

        case 'object':
            fieldHtml += renderObjectField(fieldId, propSchema, propValue || {}, configName, propPath);
            break;

        default:
            fieldHtml += `<div class="alert alert-warning">不支持的类型: ${propSchema.type}</div>`;
    }

    if (propSchema.description) {
        fieldHtml += `<small class="form-text text-muted">${propSchema.description}</small>`;
    }

    fieldHtml += '</div>';
    return fieldHtml;
}

// 渲染枚举字段
function renderEnumField(fieldId, fieldName, schema, value, required) {
    return `
        <select class="form-control" id="${fieldId}" name="${fieldName}" ${required ? 'required' : ''}>
            <option value="">-- 请选择 --</option>
            ${schema.enum.map(option => `
                <option value="${option}" ${value === option ? 'selected' : ''}>${option}</option>
            `).join('')}
        </select>
    `;
}

// 渲染密码字段
function renderPasswordField(fieldId, fieldName, value, required) {
    return `
        <input type="password" class="form-control" id="${fieldId}" name="${fieldName}" 
            value="${value || ''}" ${required ? 'required' : ''}>
    `;
}

// 渲染文本区域字段
function renderTextareaField(fieldId, fieldName, value, required) {
    return `
        <textarea class="form-control" id="${fieldId}" name="${fieldName}" 
            rows="4" ${required ? 'required' : ''}>${value || ''}</textarea>
    `;
}

// 渲染文本字段
function renderTextField(fieldId, fieldName, value, required) {
    return `
        <input type="text" class="form-control" id="${fieldId}" name="${fieldName}" 
            value="${value || ''}" ${required ? 'required' : ''}>
    `;
}

// 渲染数字字段
function renderNumberField(fieldId, fieldName, schema, value, required) {
    return `
        <input type="number" class="form-control" id="${fieldId}" name="${fieldName}" 
            value="${value !== undefined ? value : ''}" 
            ${schema.minimum !== undefined ? `min="${schema.minimum}"` : ''} 
            ${schema.maximum !== undefined ? `max="${schema.maximum}"` : ''} 
            ${required ? 'required' : ''}>
    `;
}

// 渲染布尔字段
function renderBooleanField(fieldId, fieldName, value) {
    return `
        <div class="form-check">
            <input type="checkbox" class="form-check-input" id="${fieldId}" name="${fieldName}" 
                ${value ? 'checked' : ''}>
            <label class="form-check-label" for="${fieldId}">启用</label>
        </div>
    `;
}

// 渲染数组字段
function renderArrayField(fieldId, schema, value, configName, propPath) {
    let html = `
        <div class="array-container" id="${fieldId}-container">
            <div class="array-items">
    `;

    if (value && value.length > 0) {
        value.forEach((item, index) => {
            html += renderArrayItem(fieldId, schema, item, index, configName, propPath);
        });
    }

    html += `
            </div>
            <div class="array-controls">
                <button type="button" class="btn btn-sm btn-primary add-array-item" 
                    data-field-id="${fieldId}" data-config="${configName}" data-path="${propPath}">
                    <i class="fas fa-plus"></i> 添加项
                </button>
            </div>
        </div>
    `;

    return html;
}

// 渲染数组项
function renderArrayItem(fieldId, schema, value, index, configName, propPath) {
    const itemId = `${fieldId}-item-${index}`;
    const itemName = `${configName}[${propPath}][${index}]`;

    let html = `
        <div class="array-item" data-index="${index}">
    `;

    if (schema.items.type === 'string') {
        html += `
            <input type="text" class="form-control" id="${itemId}" name="${itemName}" value="${value || ''}">
        `;
    } else if (schema.items.type === 'number' || schema.items.type === 'integer') {
        html += `
            <input type="number" class="form-control" id="${itemId}" name="${itemName}" value="${value || 0}">
        `;
    } else if (schema.items.type === 'object') {
        html += `
            <div class="object-property w-100">
                ${renderSchemaProperties(schema.items, value || {}, configName, `${propPath}[${index}]`)}
            </div>
        `;
    }

    html += `
            <button type="button" class="btn btn-sm btn-danger remove-array-item ml-2">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    `;

    return html;
}

// 渲染对象字段
function renderObjectField(fieldId, schema, value, configName, propPath) {
    return `
        <div class="object-container">
            <div class="object-properties">
                ${renderSchemaProperties(schema, value, configName, propPath)}
            </div>
        </div>
    `;
}

// 处理添加数组项
async function handleAddArrayItem(fieldId, configName, propPath) {
    try {
        const container = document.querySelector(`#${fieldId}-container .array-items`);
        const index = container.children.length;

        const response = await fetch('/config/api/schemas');
        const data = await response.json();

        if (data.code === 0 && data.data) {
            const schemas = data.data;
            const schema = schemas[configName];

            if (!schema) {
                throw new Error(`未找到配置 '${configName}' 的schema`);
            }

            // 找到数组的schema
            const pathParts = propPath.split('.');
            let currentSchema = schema;

            for (const part of pathParts) {
                if (currentSchema.properties && currentSchema.properties[part]) {
                    currentSchema = currentSchema.properties[part];
                } else {
                    throw new Error(`在路径 '${propPath}' 中未找到部分 '${part}' 的schema`);
                }
            }

            if (currentSchema.type !== 'array') {
                throw new Error(`路径 '${propPath}' 的schema不是数组类型`);
            }

            if (!currentSchema.items) {
                throw new Error('数组schema缺少items定义');
            }

            const newItem = renderArrayItem(fieldId, currentSchema, null, index, configName, propPath);
            container.insertAdjacentHTML('beforeend', newItem);
        } else {
            throw new Error(data.msg || '获取schema失败');
        }
    } catch (error) {
        console.error('添加数组项失败:', error);
        showNotification(error.message, 'error');
    }
}

// 保存所有配置
async function saveAllConfigs() {
    const configs = {};
    const saveButton = document.getElementById('saveConfig');
    const originalBtnText = saveButton.innerHTML;

    try {
        // 验证表单
        if (!validateForm()) {
            saveButton.disabled = false;
            saveButton.innerHTML = originalBtnText;
            isSaving = false;
            return;
        }

        // 收集所有配置
        document.querySelectorAll('.config-section').forEach(section => {
            const configName = section.dataset.config;
            configs[configName] = collectConfigData(configName);
        });

        const configNames = Object.keys(configs);
        let failedConfigs = 0;

        // 逐个保存配置
        for (let i = 0; i < configNames.length; i++) {
            const configName = configNames[i];
            const progress = Math.round((i / configNames.length) * 100);

            saveButton.innerHTML = `<i class="fas fa-spinner fa-spin"></i> 保存中 ${progress}%`;

            try {
                const success = await saveConfig(configName, configs[configName]);
                if (!success) failedConfigs++;
            } catch (error) {
                console.error(`保存配置 ${configName} 失败:`, error);
                failedConfigs++;
            }
        }

        // 显示保存结果
        if (failedConfigs > 0) {
            showNotification(`保存完成，但有 ${failedConfigs} 个配置保存失败`, 'error');
        } else {
            showNotification('所有配置保存成功', 'success');
        }
    } catch (error) {
        console.error('保存配置失败:', error);
        showNotification('保存配置失败: ' + error.message, 'error');
    } finally {
        saveButton.disabled = false;
        saveButton.innerHTML = originalBtnText;
        isSaving = false;
    }
}

// 验证表单
function validateForm() {
    const requiredInputs = document.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;
    let firstInvalidElement = null;

    // 清除之前的验证错误提示
    document.querySelectorAll('.invalid-feedback').forEach(el => el.remove());
    document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

    // 验证每个必填字段
    requiredInputs.forEach(input => {
        const value = input.value;

        if (!value || value.trim() === '') {
            isValid = false;
            input.classList.add('is-invalid');

            const feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            feedback.textContent = '此字段不能为空';
            input.parentNode.appendChild(feedback);

            if (!firstInvalidElement) {
                firstInvalidElement = input;
            }
        }
    });

    // 滚动到第一个错误字段
    if (!isValid && firstInvalidElement) {
        firstInvalidElement.scrollIntoView({behavior: 'smooth', block: 'center'});
        showNotification('表单验证失败，请检查必填字段', 'error');
    }

    return isValid;
}

// 收集配置数据
function collectConfigData(configName) {
    const config = {};

    document.querySelectorAll(`[name^="${configName}["]`).forEach(input => {
        const name = input.getAttribute('name');
        const path = name.match(/\[(.*?)\]/)[1];
        const value = getInputValue(input);

        setNestedProperty(config, path, value);
    });

    return config;
}

// 获取输入值
function getInputValue(input) {
    const type = input.getAttribute('type');

    if (type === 'checkbox') {
        return input.checked;
    } else if (type === 'number') {
        return input.value ? Number(input.value) : null;
    } else {
        return input.value;
    }
}

// 设置嵌套属性
function setNestedProperty(obj, path, value) {
    const parts = path.split(/\.|\[|\]/).filter(Boolean);
    let current = obj;

    for (let i = 0; i < parts.length - 1; i++) {
        const part = parts[i];

        if (!isNaN(part)) {
            if (!Array.isArray(current)) {
                current = [];
            }
        } else if (current[part] === undefined) {
            current[part] = {};
        }

        current = current[part];
    }

    const lastPart = parts[parts.length - 1];
    current[lastPart] = value;
}

// 保存单个配置
async function saveConfig(configName, configData) {
    try {
        const response = await fetch(`/config/api/config/${configName}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(configData)
        });

        const data = await response.json();
        return data.code === 0;
    } catch (error) {
        console.error(`保存配置 ${configName} 失败:`, error);
        return false;
    }
} 