import { PromptEditor } from '@/components/prompt-editor';
import { SettingOutlined } from '@ant-design/icons';
import {
  Button,
  Form,
  FormInstance,
  Input,
  InputNumber,
  Modal,
  Radio,
  Select,
  Switch,
} from 'antd';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { IOperatorForm } from '../../interface';

// 预设服务器配置
const PRESET_SERVERS = {
  'tavily-mcp': {
    command: 'npx',
    args: ['-y', 'tavily-mcp@0.1.2'],
    env: {
      TAVILY_API_KEY: 'your-api-key-here',
    },
  },
  'amap-maps': {
    command: 'npx',
    args: ['-y', '@amap/amap-maps-mcp-server'],
    env: {
      AMAP_MAPS_API_KEY: 'your-api-key-here',
    },
  },
  custom: {
    env: {}, // 确保初始值为空对象
  },
};

const ServerConfigForm = ({ form }: { form: FormInstance }) => {
  const serverType =
    Form.useWatch(['server_config', 'type'], form) || 'command';
  const envValue = Form.useWatch(['server_config', 'env'], form) || {};
  const [envString, setEnvString] = useState(() => {
    const initialEnv = form.getFieldValue(['server_config', 'env']) || {};
    return JSON.stringify(initialEnv, null, 2);
  });

  useEffect(() => {
    setEnvString(JSON.stringify(envValue, null, 2));
  }, [envValue]);

  return (
    <>
      {/* 服务器配置类型选择 */}
      <Form.Item
        name={['server_config', 'type']}
        label="服务器配置类型"
        tooltip="选择服务器配置的类型"
      >
        <Radio.Group buttonStyle="solid">
          <Radio.Button value="command">命令行模式</Radio.Button>
          <Radio.Button value="url">URL模式</Radio.Button>
        </Radio.Group>
      </Form.Item>

      {serverType === 'command' && (
        <>
          <Form.Item
            name={['server_config', 'command']}
            label="执行命令"
            rules={[
              {
                required: true,
                message: '请输入执行命令（如npx）',
              },
            ]}
          >
            <Input placeholder="例：npx" />
          </Form.Item>
          <Form.Item
            name={['server_config', 'args']}
            label="参数"
            rules={[
              {
                validator: (_, value) =>
                  !value || Array.isArray(value)
                    ? Promise.resolve()
                    : Promise.reject('参数必须是数组'),
              },
            ]}
          >
            <Select mode="tags" placeholder="输入参数，按回车确认" />
          </Form.Item>
        </>
      )}

      {serverType === 'url' && (
        <>
          <Form.Item
            name={['server_config', 'url']}
            label="SSE服务地址"
            rules={[
              { required: true },
              {
                pattern: /^https?:\/\//,
                message: '必须以http://或https://开头',
              },
            ]}
          >
            <Input placeholder="例：https://api.example.com/sse" />
          </Form.Item>

          <Form.Item
            name={['server_config', 'headers']}
            label="请求头"
            tooltip="JSON格式的HTTP头"
            rules={[
              {
                validator: (_, value) => {
                  try {
                    JSON.parse(value || '{}');
                    return Promise.resolve();
                  } catch {
                    return Promise.reject('必须是有效的JSON格式');
                  }
                },
              },
            ]}
            getValueFromEvent={(e) => {
              try {
                return JSON.parse(e.target.value || '{}');
              } catch {
                return form.getFieldValue(['server_config', 'headers']) || {};
              }
            }}
            getValueProps={(value) => ({
              value:
                typeof value === 'object'
                  ? JSON.stringify(value, null, 2)
                  : value,
            })}
          >
            <Input.TextArea
              placeholder='{"Content-Type": "application/json"}'
              autoSize={{ minRows: 2 }}
            />
          </Form.Item>

          <Form.Item
            name={['server_config', 'timeout']}
            label="连接超时（秒）"
            initialValue={5}
            rules={[
              {
                type: 'number',
                min: 1,
                max: 60,
                message: '请输入1-60之间的数字',
              },
            ]}
          >
            <InputNumber step={1} />
          </Form.Item>

          <Form.Item
            name={['server_config', 'sse_read_timeout']}
            label="读取超时（秒）"
            initialValue={300}
            rules={[
              {
                type: 'number',
                min: 10,
                max: 3600,
                message: '请输入10-3600之间的数字',
              },
            ]}
          >
            <InputNumber step={10} />
          </Form.Item>
        </>
      )}

      {serverType === 'command' && (
        <Form.Item
          name={['server_config', 'env']}
          label="环境变量"
          tooltip="JSON格式的环境变量配置"
          getValueFromEvent={(e) => {
            try {
              return JSON.parse(e.target.value || '{}');
            } catch {
              return form.getFieldValue(['server_config', 'env']) || {};
            }
          }}
          getValueProps={(value) => ({
            value:
              typeof value === 'object'
                ? JSON.stringify(value, null, 2)
                : value,
          })}
        >
          <Input.TextArea
            placeholder='{"KEY": "VALUE"}'
            autoSize={{ minRows: 3 }}
          />
        </Form.Item>
      )}
    </>
  );
};

const ServerConfigModal = ({
  form,
  visible,
  onClose,
}: {
  form: FormInstance;
  visible: boolean;
  onClose: () => void;
}) => {
  return (
    <Modal
      title="服务器高级配置"
      open={visible}
      onCancel={onClose}
      footer={null}
      width={800}
    >
      <ServerConfigForm form={form} />
    </Modal>
  );
};

const McpForm = ({ onValuesChange, form }: IOperatorForm) => {
  const { t } = useTranslation('flow');
  const [showServerConfig, setShowServerConfig] = useState(false);

  // 修改后的 useEffect
  useEffect(() => {
    const initialPreset = 'tavily-mcp';
    const selected = PRESET_SERVERS[initialPreset];

    form?.setFieldsValue({
      serverPreset: initialPreset,
      server_config: {
        type: 'command',
        ...selected,
        env: selected.env || {},
      },
    });
  }, [form]);

  // 修改后的 handleValuesChange
  const handleValuesChange = (changedValues: any, allValues: any) => {
    console.group('值变更追踪');
    console.log('变更字段:', Object.keys(changedValues));
    console.log('变更详情:', changedValues);

    // 处理预设变更
    if (changedValues.serverPreset) {
      const selected =
        PRESET_SERVERS[
          changedValues.serverPreset as keyof typeof PRESET_SERVERS
        ];
      console.log('应用新预设:', selected);

      // 确定配置类型
      const isUrlMode = 'url' in selected;

      // 构建新的配置
      const newConfig = {
        // 基础配置
        type: isUrlMode ? 'url' : 'command',

        // URL模式特有字段
        ...(isUrlMode
          ? {
              url: selected.url,
              headers: selected.headers || {},
              timeout: selected.timeout || 5,
              sse_read_timeout: selected.sse_read_timeout || 300,
            }
          : {}),

        // 命令行模式特有字段
        ...(!isUrlMode
          ? {
              command: selected.command,
              args: selected.args || [],
              env: selected.env || {},
            }
          : {}),
      };

      console.log('新配置:', newConfig);

      // 更新表单
      form?.setFieldsValue({
        server_config: newConfig,
      });

      // 触发值变更回调
      onValuesChange?.(
        { server_config: newConfig },
        { ...allValues, server_config: newConfig },
      );

      console.log('表单更新完成');
      return;
    }

    // 统一处理其他字段变更
    onValuesChange?.(changedValues, allValues);
    console.groupEnd();
  };

  return (
    <Form
      name="mcp-config"
      autoComplete="off"
      form={form}
      onValuesChange={handleValuesChange}
      layout="vertical"
      initialValues={{
        cite: false,
        // prompt: '你是一个有用的助理',
        history_window: 5,
        serverPreset: 'tavily-mcp',
        server_config: {
          type: 'command',
          ...PRESET_SERVERS['tavily-mcp'],
        },
      }}
    >
      {/* 系统提示 */}
      <Form.Item
        name="prompt"
        label={t('systemPrompt')}
        tooltip={t('promptTip', { keyPrefix: 'knowledgeConfiguration' })}
        rules={[{ required: true, message: t('promptMessage') }]}
      >
        <PromptEditor
          value={form?.getFieldValue('prompt')}
          onChange={(value) => form?.setFieldValue('prompt', value)}
        />
      </Form.Item>

      {/* 服务器配置选择器 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Form.Item
          name="serverPreset"
          label="服务器配置方案"
          tooltip="选择预配置方案或自定义配置"
          style={{ flex: 1, marginBottom: 24 }}
        >
          <Select
            options={[
              { value: 'tavily-mcp', label: 'Tavily 搜索引擎' },
              { value: 'amap-maps', label: '高德地图服务' },
              { value: 'custom', label: '自定义配置' },
            ]}
          />
        </Form.Item>
        <Button
          type="link"
          icon={<SettingOutlined />}
          onClick={() => setShowServerConfig(true)}
          style={{ marginTop: 6 }}
        />
      </div>

      {/* 动态服务器配置表单 */}
      <ServerConfigModal
        form={form!}
        visible={showServerConfig}
        onClose={() => setShowServerConfig(false)}
      />

      {/* 引用开关 */}
      <Form.Item
        name="cite"
        label={t('enableCitation')}
        valuePropName="checked"
        tooltip="是否在回答中显示引用来源"
      >
        <Switch />
      </Form.Item>

      {/* 历史窗口 */}
      <Form.Item
        name="history_window"
        label={t('historyWindow')}
        tooltip="保留的对话历史轮数"
      >
        <InputNumber min={0} max={20} />
      </Form.Item>
    </Form>
  );
};

export default McpForm;
