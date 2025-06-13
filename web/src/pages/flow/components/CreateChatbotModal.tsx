import request, { get, post } from '@/utils/request';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import {
  Button,
  Empty,
  List,
  message,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Tag,
  Tooltip,
} from 'antd';
import { FC, useEffect, useState } from 'react';
import AddChatbotModal from './AddChatbotModal';

interface ChatbotItem {
  canvas_id: string;
  client_id: string;
  client_secret: string;
  user_id: string;
  status: 'running' | 'stop' | 'error';
}

interface ApiResponse {
  code: number;
  data: ChatbotItem[];
  message: string;
}

interface UserInfo {
  id: string;
  // 可能的其他用户信息字段
}

interface CreateChatbotModalProps {
  visible: boolean;
  onCancel: () => void;
  agentId: string;
}

const CreateChatbotModal: FC<CreateChatbotModalProps> = ({
  visible,
  onCancel,
  agentId,
}) => {
  const [chatbots, setChatbots] = useState<ChatbotItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [addLoading, setAddLoading] = useState(false);
  // 存储当前正在操作的机器人ID
  const [operatingBotId, setOperatingBotId] = useState<string | null>(null);
  // 添加当前用户ID状态
  const [currentUserId, setCurrentUserId] = useState<string>('');

  // 获取当前用户信息
  const fetchCurrentUser = async () => {
    try {
      const { data: responseData } = await get('/v1/user/info');
      if (responseData && responseData.code === 0 && responseData.data) {
        setCurrentUserId(responseData.data.id);
      }
    } catch (error) {
      console.error('获取当前用户信息失败', error);
    }
  };

  const fetchChatbots = async () => {
    if (!visible || !agentId) return;

    try {
      setLoading(true);
      const { data: responseData } = await get(`/v1/chatbot/list/${agentId}`);
      if (
        responseData &&
        responseData.code === 0 &&
        Array.isArray(responseData.data)
      ) {
        setChatbots(responseData.data);
      } else {
        message.error(
          '获取聊天机器人列表失败: ' + (responseData.message || '未知错误'),
        );
      }
    } catch (error) {
      console.error('获取聊天机器人列表失败', error);
      message.error('获取聊天机器人列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible) {
      fetchCurrentUser();
      fetchChatbots();
    }
  }, [visible, agentId]);

  const handleDelete = async (client_id: string) => {
    try {
      setOperatingBotId(client_id);
      const { data: responseData } = await request.delete(
        `/v1/chatbot/delete/${client_id}`,
      );
      if (responseData && responseData.code === 0) {
        message.success('删除成功');
        fetchChatbots();
      } else {
        message.error('删除失败: ' + (responseData.message || '未知错误'));
      }
    } catch (error) {
      console.error('删除聊天机器人失败', error);
      message.error('删除聊天机器人失败');
    } finally {
      setOperatingBotId(null);
    }
  };

  const handleEnable = async (client_id: string) => {
    try {
      setOperatingBotId(client_id);
      const { data: responseData } = await post(
        `/chatbots/${client_id}/start`,
        {},
      );
      if (responseData && responseData.status === 'running') {
        message.success('启用成功');
        fetchChatbots();
      } else {
        message.error('启用失败');
      }
    } catch (error) {
      console.error('启用聊天机器人失败', error);
      message.error('启用聊天机器人失败');
    } finally {
      setOperatingBotId(null);
    }
  };

  const handleStop = async (client_id: string) => {
    try {
      setOperatingBotId(client_id);
      const { data: responseData } = await post(
        `/chatbots/${client_id}/stop`,
        {},
      );
      if (responseData && responseData.status === 'stop') {
        message.success('停止成功');
        fetchChatbots();
      } else {
        message.error('停止失败');
      }
    } catch (error) {
      console.error('停止聊天机器人失败', error);
      message.error('停止聊天机器人失败');
    } finally {
      setOperatingBotId(null);
    }
  };

  const handleShowAddModal = () => {
    setAddModalVisible(true);
  };

  const handleCancelAddModal = () => {
    setAddModalVisible(false);
  };

  const handleAddChatbot = async (values: {
    clientId: string;
    clientSecret: string;
  }) => {
    try {
      setAddLoading(true);
      const { data: responseData } = await post(`/v1/chatbot/add`, {
        canvas_id: agentId,
        client_id: values.clientId,
        client_secret: values.clientSecret,
      });

      if (responseData && responseData.code === 0) {
        message.success('添加成功');
        setAddModalVisible(false);
        fetchChatbots();
      } else {
        message.error('添加失败: ' + (responseData.message || '未知错误'));
      }
    } catch (error) {
      console.error('添加聊天机器人失败', error);
      message.error('添加聊天机器人失败');
    } finally {
      setAddLoading(false);
    }
  };

  // 只显示Client ID最后5位和前2位作为掩码
  const maskClientSecret = (secret: string) => {
    if (!secret) return '';
    if (secret.length <= 8) return '*'.repeat(secret.length);
    return `${secret.substring(0, 2)}${'*'.repeat(20)}${secret.substring(secret.length - 5)}`;
  };

  // 根据状态渲染图标和文字
  const renderStatus = (status: string) => {
    switch (status) {
      case 'running':
        return (
          <Tooltip title="运行中">
            <Tag color="success" icon={<CheckCircleOutlined />}>
              运行中
            </Tag>
          </Tooltip>
        );
      case 'stop':
        return (
          <Tooltip title="已停止">
            <Tag color="default" icon={<PauseCircleOutlined />}>
              已停止
            </Tag>
          </Tooltip>
        );
      case 'error':
        return (
          <Tooltip title="出错">
            <Tag color="error" icon={<CloseCircleOutlined />}>
              出错
            </Tag>
          </Tooltip>
        );
      default:
        return <Tag color="default">未知状态</Tag>;
    }
  };

  // 检查是否是当前用户创建的聊天机器人
  const isOwnedByCurrentUser = (item: ChatbotItem) => {
    return item.user_id === currentUserId;
  };

  // 渲染操作按钮
  const renderActionButtons = (item: ChatbotItem) => {
    const isOperating = operatingBotId === item.client_id;
    const isOwner = isOwnedByCurrentUser(item);

    // 如果不是当前用户创建的聊天机器人，不显示任何操作按钮
    if (!isOwner) {
      return;
    }

    return (
      <Space size="middle">
        {/* 状态为running时显示停止按钮 */}
        {item.status === 'running' && (
          <Tooltip title="停止">
            <Button
              type="text"
              icon={<PauseCircleOutlined style={{ color: '#ff4d4f' }} />}
              onClick={() => handleStop(item.client_id)}
              loading={isOperating}
              disabled={isOperating}
            />
          </Tooltip>
        )}

        {/* 状态为stop或error时显示启用按钮 */}
        {(item.status === 'stop' || item.status === 'error') && (
          <Tooltip title="启用">
            <Button
              type="text"
              icon={<PlayCircleOutlined style={{ color: '#52c41a' }} />}
              onClick={() => handleEnable(item.client_id)}
              loading={isOperating}
              disabled={isOperating}
            />
          </Tooltip>
        )}

        {/* 删除按钮始终显示 */}
        <Popconfirm
          title="确定要删除这个聊天机器人绑定吗？"
          onConfirm={() => handleDelete(item.client_id)}
          okText="确定"
          cancelText="取消"
          disabled={isOperating}
        >
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            loading={isOperating}
            disabled={isOperating}
          >
            删除
          </Button>
        </Popconfirm>
      </Space>
    );
  };

  return (
    <>
      <Modal
        title="聊天机器人管理"
        open={visible}
        onCancel={onCancel}
        footer={[
          <Button key="close" onClick={onCancel}>
            关闭
          </Button>,
        ]}
        width={700}
      >
        <Spin spinning={loading}>
          {chatbots.length === 0 ? (
            <Empty description="暂无绑定的聊天机器人" />
          ) : (
            <List
              itemLayout="horizontal"
              dataSource={chatbots}
              renderItem={(item) => (
                <List.Item actions={[renderActionButtons(item)]}>
                  <List.Item.Meta
                    title={
                      <div className="flex items-center gap-2">
                        <span>应用 ID: {item.client_id}</span>
                        {renderStatus(item.status)}
                        {isOwnedByCurrentUser(item) && (
                          <Tag color="blue">我创建的</Tag>
                        )}
                      </div>
                    }
                    description={
                      <div>
                        <div>密钥: {maskClientSecret(item.client_secret)}</div>
                      </div>
                    }
                  />
                </List.Item>
              )}
            />
          )}
          <div className="mt-4 flex justify-center">
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={handleShowAddModal}
            >
              添加绑定
            </Button>
          </div>
        </Spin>
      </Modal>

      <AddChatbotModal
        visible={addModalVisible}
        onCancel={handleCancelAddModal}
        onSubmit={handleAddChatbot}
        loading={addLoading}
      />
    </>
  );
};

export default CreateChatbotModal;
