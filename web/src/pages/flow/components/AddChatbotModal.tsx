import { Button, Form, Input, Modal, Typography } from 'antd';
import { FC } from 'react';

const { Paragraph, Text } = Typography;

interface AddChatbotModalProps {
  visible: boolean;
  onCancel: () => void;
  onSubmit: (values: { clientId: string; clientSecret: string }) => void;
  loading?: boolean;
}

const AddChatbotModal: FC<AddChatbotModalProps> = ({
  visible,
  onCancel,
  onSubmit,
  loading = false,
}) => {
  const [form] = Form.useForm();

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      onSubmit(values);
      form.resetFields();
    });
  };

  return (
    <Modal
      title="添加聊天机器人绑定"
      open={visible}
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button
          key="submit"
          type="primary"
          onClick={handleSubmit}
          loading={loading}
        >
          确认添加
        </Button>,
      ]}
      width={550}
    >
      <Paragraph className="mb-4">
        <Text>
          将此Agent绑定为第三方应用的聊天机器人，您需要先在开放平台创建应用并获取应用凭证。
        </Text>
      </Paragraph>

      <Form form={form} layout="vertical">
        <Form.Item
          name="clientId"
          label="应用 ID (Client ID)"
          rules={[{ required: true, message: '请输入应用ID' }]}
        >
          <Input placeholder="请输入开放平台获取的应用ID" />
        </Form.Item>
        <Form.Item
          name="clientSecret"
          label="应用密钥 (Client Secret)"
          rules={[{ required: true, message: '请输入应用密钥' }]}
        >
          <Input.Password placeholder="请输入开放平台获取的应用密钥" />
        </Form.Item>
        <div className="text-sm text-gray-500 mt-4 p-3 bg-gray-50 rounded">
          <Text type="secondary">
            前往{' '}
            <a
              href="https://open-dev.digntalk.com"
              target="_blank"
              rel="noopener noreferrer"
            >
              https://open-dev.digntalk.com
            </a>{' '}
            创建应用后获取应用凭证。完成绑定后，您可以在第三方平台将此Agent作为聊天机器人使用。
          </Text>
        </div>
      </Form>
    </Modal>
  );
};

export default AddChatbotModal;
