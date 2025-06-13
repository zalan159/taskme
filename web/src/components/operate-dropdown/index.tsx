import conf from '@/conf.json';
import { useShowDeleteConfirm } from '@/hooks/common-hooks';
import { useFetchAgentInfo, useUpdateAgentInfo } from '@/hooks/flow-hooks';
import { useListTenant } from '@/hooks/user-setting-hooks';
import {
  DeleteOutlined,
  EditOutlined,
  ExclamationCircleOutlined,
  LikeFilled,
  LikeOutlined,
  MoreOutlined,
} from '@ant-design/icons';
import {
  Dropdown,
  Input,
  MenuProps,
  Modal,
  Select,
  Space,
  Tag,
  message,
} from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import styles from './index.less';

interface IProps {
  deleteItem: () => Promise<any> | void;
  iconFontSize?: number;
  iconFontColor?: string;
  items?: MenuProps['items'];
  height?: number;
  needsDeletionValidation?: boolean;
  agentId?: string;
}

const OperateDropdown = ({
  deleteItem,
  children,
  iconFontSize = 30,
  iconFontColor = 'gray',
  items: otherItems = [],
  height = 24,
  needsDeletionValidation = true,
  agentId,
}: React.PropsWithChildren<IProps>) => {
  console.log('OperateDropdown rendered with agentId:', agentId);

  const { t } = useTranslation();
  const showDeleteConfirm = useShowDeleteConfirm();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [permission, setPermission] = useState<'private' | 'team' | 'public'>(
    'private',
  );
  const [tempPermission, setTempPermission] = useState<
    'private' | 'team' | 'public'
  >('private');
  const [showPermissionConfirm, setShowPermissionConfirm] = useState(false);
  const [industry, setIndustry] = useState<string>('');
  const [tags, setTags] = useState<string[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [tagColors, setTagColors] = useState<{ [key: string]: string }>({});
  const [selectedTeams, setSelectedTeams] = useState<string[]>([]);
  const {
    data: agentInfo,
    loading: fetchingAgentInfo,
    refetch,
  } = agentId
    ? useFetchAgentInfo(agentId)
    : { data: null, loading: false, refetch: () => Promise.resolve() };
  const { updateAgentInfo } = useUpdateAgentInfo();
  const { data: teams, loading: teamsLoading } = useListTenant();
  const [isCreator, setIsCreator] = useState(false);
  const [isRecommended, setIsRecommended] = useState(false);

  const isAgentCard = Boolean(agentId);

  // 检查是否是创建者 和 初始化 isRecommended 状态
  useEffect(() => {
    // Log agentId for context, even if agentInfo is not yet available
    // console.log(`[OperateDropdown] useEffect triggered. agentId: ${agentId}, loading: ${fetchingAgentInfo}`);

    if (
      agentInfo &&
      Object.keys(agentInfo).length > 0 &&
      agentInfo.user_id !== undefined
    ) {
      // Check if agentInfo is populated
      console.log(
        `[OperateDropdown 初始化] agentId: ${agentId} - 接收到 agentInfo:`,
        agentInfo,
      );

      const currentUserId = localStorage.getItem('userId');
      const creatorCheck = agentInfo.user_id === currentUserId;
      setIsCreator(creatorCheck);
      console.log(
        `[OperateDropdown 初始化] agentId: ${agentId} - 是否为创建者: ${creatorCheck} (当前用户: ${currentUserId}, 创建者: ${agentInfo.user_id})`,
      );

      console.log(
        `[OperateDropdown 初始化] agentId: ${agentId} - 开始设置推荐状态。从 agentInfo 获取的 is_recommended: ${agentInfo.is_recommended}`,
      );
      if (typeof agentInfo.is_recommended === 'boolean') {
        setIsRecommended(agentInfo.is_recommended);
        console.log(
          `[OperateDropdown 初始化] agentId: ${agentId} - 本地 isRecommended 状态已设置为: ${agentInfo.is_recommended}`,
        );
      } else {
        // 如果 agentInfo.is_recommended 未定义或不是布尔值，则根据默认值设置或保持当前状态
        // 在这种情况下，我们通常会依赖 DEFAULT_AGENT_INFO 中 is_recommended 的默认值 (false)
        // 或者如果 useFetchAgentInfo 总是返回一个确定的布尔值（即使是默认的），这里可能不需要特别处理
        setIsRecommended(false); // 或者 agentInfo.is_recommended || false 如果它可能是null/undefined但我们希望false
        console.log(
          `[OperateDropdown 初始化] agentId: ${agentId} - agentInfo.is_recommended 不是布尔值或未定义 (值: ${agentInfo.is_recommended})。本地 isRecommended 状态设置为默认 false。`,
        );
      }
    } else if (agentId && fetchingAgentInfo) {
      console.log(
        `[OperateDropdown 初始化] agentId: ${agentId} - 正在获取 agentInfo...`,
      );
    } else if (
      agentId &&
      !fetchingAgentInfo &&
      (!agentInfo || Object.keys(agentInfo).length === 0)
    ) {
      console.warn(
        `[OperateDropdown 初始化] agentId: ${agentId} - agentInfo 获取完成但为空或无效:`,
        agentInfo,
      );
      // 在这种情况下，可能也需要设置一个默认的推荐状态
      setIsRecommended(false);
      setIsCreator(false);
      console.log(
        `[OperateDropdown 初始化] agentId: ${agentId} - 由于 agentInfo 为空，isRecommended 设置为 false, isCreator 设置为 false。`,
      );
    }
  }, [agentInfo, agentId, fetchingAgentInfo]); // fetchingAgentInfo added to help log loading state

  // 预设的颜色列表
  const colors = [
    'blue',
    'green',
    'orange',
    'red',
    'purple',
    'cyan',
    'magenta',
    'gold',
    'lime',
    'volcano',
  ];

  // 从配置文件获取行业选项
  const industryOptions = conf.industryOptions;

  // 初始化标签颜色
  const initializeTagColors = (tagList: string[]) => {
    const newColors: { [key: string]: string } = {};
    tagList.forEach((tag) => {
      if (!tagColors[tag]) {
        newColors[tag] = colors[Math.floor(Math.random() * colors.length)];
      }
    });
    setTagColors((prev) => ({ ...prev, ...newColors }));
  };

  // 当 Modal 打开时，初始化数据
  useEffect(() => {
    if (isModalOpen && agentInfo) {
      setPermission(agentInfo.permission);
      setTempPermission(agentInfo.permission);
      setIndustry(agentInfo.canvas_industry || '');
      setTags(agentInfo.tags || []);
      initializeTagColors(agentInfo.tags || []);
      if (agentInfo.team_ids) {
        setSelectedTeams(agentInfo.team_ids);
      }
    }
  }, [isModalOpen, agentInfo]);

  useEffect(() => {
    if (isModalOpen) {
      const handleClick = (e: MouseEvent) => {
        const target = e.target as HTMLElement;
        // 如果是 Modal 的关闭按钮、取消按钮、确认按钮、标签的关闭按钮或标签本身，不阻止事件
        if (
          target.closest('.ant-modal-close') ||
          target.closest('.ant-btn-default') ||
          target.closest('.ant-btn-primary') ||
          target.closest('.anticon-close') ||
          target.closest('.ant-tag') ||
          target.closest('.ant-tag-close-icon') ||
          target.closest('.ant-select') ||
          target.closest('.ant-input')
        ) {
          return;
        }
        // 如果是 Modal 内容区域，阻止事件冒泡
        if (target.closest('.ant-modal-root')) {
          e.stopPropagation();
        }
      };

      document.addEventListener('click', handleClick, true);
      return () => {
        document.removeEventListener('click', handleClick, true);
      };
    }
  }, [isModalOpen]);

  const handleDelete = () => {
    if (needsDeletionValidation) {
      showDeleteConfirm({ onOk: deleteItem });
    } else {
      deleteItem();
    }
  };

  const handlePermissionChange = (value: 'private' | 'team' | 'public') => {
    const newPermission = value;

    // 任何权限变更都需要确认
    if (permission !== newPermission) {
      Modal.confirm({
        title: '修改权限确认',
        icon: <ExclamationCircleOutlined />,
        content: `修改Agent权限为${newPermission === 'public' ? '公开' : newPermission === 'team' ? '团队' : '私有'}后，所有关联的知识库将一起修改权限且无法撤回`,
        okText: '确认',
        cancelText: '取消',
        onOk: (close) => {
          setPermission(newPermission);
          close();
        },
        onCancel: () => {
          // Do nothing, keep the original permission
        },
      });
    }
  };

  const handleOk = async (e?: React.MouseEvent<HTMLElement>) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }

    try {
      // 当权限为team时，确保team_ids不为空
      if (
        permission === 'team' &&
        (!selectedTeams || selectedTeams.length === 0)
      ) {
        message.error('请选择至少一个团队');
        return;
      }

      if (!agentId) {
        console.error('Cannot update agent info: agentId is undefined');
        message.error('修改Agent信息失败：缺少Agent ID');
        return;
      }

      await updateAgentInfo({
        canvas_id: agentId,
        canvas_tag: tags,
        canvas_permissions: permission,
        canvas_industry: industry,
        team_ids: permission === 'team' ? selectedTeams : undefined,
      });
      message.success('修改Agent信息成功');
      await refetch();
      setIsModalOpen(false);
    } catch (error) {
      console.error('Failed to update agent info:', error);
      message.error('修改Agent信息失败');
    }
  };

  const handleCancel = (e?: React.MouseEvent<HTMLElement>) => {
    console.log('handleCancel');
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setIsModalOpen(false);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      e.preventDefault();
      const newTag = inputValue.trim();
      if (!tags.includes(newTag)) {
        setTags([...tags, newTag]);
        // 为新标签分配一个颜色
        const randomColor = colors[Math.floor(Math.random() * colors.length)];
        setTagColors((prev) => ({
          ...prev,
          [newTag]: randomColor,
        }));
      }
      setInputValue('');
    }
  };

  const handleTagClose = (removedTag: string) => {
    console.log('handleTagClose called with tag:', removedTag);
    setTags(tags.filter((tag) => tag !== removedTag));
    // 删除标签时也删除对应的颜色
    const newColors = { ...tagColors };
    delete newColors[removedTag];
    setTagColors(newColors);
  };

  const handleIndustryChange = (value: string) => {
    setIndustry(value);
  };

  // 悬浮组件点击事件
  const handleDropdownMenuClick: MenuProps['onClick'] = async ({
    domEvent,
    key,
  }) => {
    domEvent.preventDefault();
    domEvent.stopPropagation();
    if (key === '1') {
      setIsModalOpen(true);
    }
    if (key === '2') {
      handleDelete();
    }
    if (key === '3') {
      handleToggleRecommend();
    }
  };

  // 新增的处理推荐切换的函数
  const handleToggleRecommend = async () => {
    if (!agentId) {
      message.error('无法获取智能体ID');
      console.log('[推荐操作] 错误: agentId 为空');
      return;
    }

    console.log(
      `[推荐操作] 开始切换智能体 ${agentId} 的推荐状态。当前agentInfo:`,
      agentInfo,
    );

    if (!agentInfo) {
      message.error('无法获取智能体信息，请稍后再试');
      console.log(`[推荐操作] 错误: agentInfo 为空，agentId: ${agentId}`);
      // 可以选择调用 refetch 来尝试重新获取数据
      // await refetch();
      return;
    }

    // 获取当前智能体的所有必要信息，以便更新
    const currentTags = agentInfo.tags || [];
    const currentPermission = agentInfo.permission || 'private';
    const currentIndustry = agentInfo.canvas_industry || '';
    const currentTeamIds = agentInfo.team_ids || [];
    const newIsRecommended = !isRecommended; // 切换推荐状态
    console.log(
      `[推荐操作] 智能体 ${agentId} 的新推荐状态: ${newIsRecommended}。当前本地isRecommended: ${isRecommended}`,
    );

    try {
      const loadingMessage = newIsRecommended
        ? '正在推荐...'
        : '正在取消推荐...';
      message.loading({ content: loadingMessage, key: 'recommendStatus' });
      console.log(`[推荐操作] 调用 updateAgentInfo，参数:`, {
        canvas_id: agentId,
        canvas_tag: currentTags,
        canvas_permissions: currentPermission,
        canvas_industry: currentIndustry,
        team_ids: currentTeamIds,
        is_recommended: newIsRecommended,
      });

      await updateAgentInfo({
        canvas_id: agentId,
        canvas_tag: currentTags,
        canvas_permissions: currentPermission,
        canvas_industry: currentIndustry,
        team_ids: currentTeamIds, // 确保传递 team_ids，如果权限是 team
        is_recommended: newIsRecommended,
      });
      // 更新本地状态以立即反映变化
      setIsRecommended(newIsRecommended);
      const successMessage = newIsRecommended ? '推荐成功' : '取消推荐成功';
      message.success({
        content: successMessage,
        key: 'recommendStatus',
        duration: 2,
      });
      console.log(
        `[推荐操作] 智能体 ${agentId} 推荐状态更新成功。新的本地 isRecommended: ${newIsRecommended}`,
      );

      // 刷新数据，以确保与其他地方同步（如果其他地方也显示这个状态）
      console.log(
        `[推荐操作] 调用 refetch 获取最新 agentInfo 数据，agentId: ${agentId}`,
      );
      await refetch();
      console.log(`[推荐操作] refetch 完成。`);
    } catch (error) {
      console.error('Failed to update recommendation status:', error);
      message.error({
        content: '操作失败，请重试',
        key: 'recommendStatus',
        duration: 2,
      });
      console.log(
        `[推荐操作] 智能体 ${agentId} 推荐状态更新失败。错误:`,
        error,
      );
    }
  };

  // 悬浮组件列表
  const items: MenuProps['items'] = useMemo(() => {
    const baseItems = [];

    // 只有Agent卡片才显示编辑标签按钮
    if (isAgentCard) {
      baseItems.push({
        key: '1',
        label: (
          <Space>
            {t('common.editTag')}
            <EditOutlined />
          </Space>
        ),
      });
    }

    // 添加其他自定义项
    baseItems.push(...otherItems);

    // 只有创建者可以看到删除按钮，或者是Knowledge卡片（没有agentId）
    if (isCreator || !isAgentCard) {
      baseItems.push({
        key: '2',
        label: (
          <Space>
            {t('common.delete')}
            <DeleteOutlined />
          </Space>
        ),
      });
    }

    // 添加新的"推荐"选项
    baseItems.push({
      key: '3', // 使用新的key
      label: (
        <Space>
          {isRecommended ? '取消推荐' : '推荐'} {/* 根据状态显示不同文本 */}
          {isRecommended ? (
            <LikeFilled style={{ color: '#1677ff' }} />
          ) : (
            <LikeOutlined />
          )}
        </Space>
      ),
    });

    return baseItems;
  }, [t, otherItems, isCreator, isAgentCard, isRecommended]); // 添加 isRecommended 到依赖项

  return (
    <>
      <Dropdown
        menu={{
          items,
          onClick: handleDropdownMenuClick,
        }}
      >
        {children || (
          <span className={styles.delete}>
            <MoreOutlined
              rotate={90}
              style={{
                fontSize: iconFontSize,
                color: iconFontColor,
                cursor: 'pointer',
                height,
              }}
            />
          </span>
        )}
      </Dropdown>

      {isAgentCard && (
        <>
          <Modal
            title={t('common.editTag')}
            open={isModalOpen}
            onOk={handleOk}
            onCancel={handleCancel}
            maskClosable={false}
            destroyOnClose
            closable={true}
            cancelText={t('setting.cancel')}
            okText={t('common.confirm')}
            confirmLoading={fetchingAgentInfo}
          >
            {fetchingAgentInfo ? (
              <div style={{ textAlign: 'center', padding: '20px' }}>
                Loading...
              </div>
            ) : (
              <>
                <div style={{ marginBottom: 16 }}>
                  <div style={{ marginBottom: 8 }}>
                    {t('common.permissions')}
                  </div>
                  <Select
                    value={permission}
                    onChange={handlePermissionChange}
                    style={{ width: '100%' }}
                    onClick={(e) => e.stopPropagation()}
                    disabled={!isCreator}
                  >
                    <Select.Option value="private">
                      {t('common.private')}
                    </Select.Option>
                    <Select.Option value="team">
                      {t('common.team')}
                    </Select.Option>
                    <Select.Option value="public">
                      {t('common.public')}
                    </Select.Option>
                  </Select>
                  {!isCreator && (
                    <div
                      style={{
                        color: '#999',
                        fontSize: '12px',
                        marginTop: '4px',
                      }}
                    >
                      只有创建者可以修改权限设置
                    </div>
                  )}
                </div>

                {/* 当权限为团队时显示团队选择器，仅创建者可见 */}
                {permission === 'team' && isCreator && (
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ marginBottom: 8 }}>
                      {t('common.selectVisibleTeams')}
                    </div>
                    <Select
                      mode="multiple"
                      value={selectedTeams}
                      onChange={setSelectedTeams}
                      style={{ width: '100%' }}
                      loading={teamsLoading}
                      onClick={(e) => e.stopPropagation()}
                      placeholder="请选择可见团队"
                    >
                      {teams?.map((team) => (
                        <Select.Option
                          key={team.tenant_id}
                          value={team.tenant_id}
                        >
                          {team.nickname}
                        </Select.Option>
                      ))}
                    </Select>
                    {selectedTeams.length === 0 && (
                      <div
                        style={{
                          color: '#ff4d4f',
                          fontSize: '12px',
                          marginTop: '4px',
                        }}
                      >
                        请至少选择一个团队
                      </div>
                    )}
                  </div>
                )}

                <div style={{ marginBottom: 16 }}>
                  <div style={{ marginBottom: 8 }}>行业</div>
                  <Select
                    value={industry}
                    onChange={handleIndustryChange}
                    style={{ width: '100%' }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {industryOptions.map((option) => (
                      <Select.Option key={option.value} value={option.value}>
                        {option.label}
                      </Select.Option>
                    ))}
                  </Select>
                </div>
                <div>
                  <div style={{ marginBottom: 8 }}>{t('common.tags')}</div>
                  <div style={{ marginBottom: 8 }}>
                    {tags.map((tag) => (
                      <Tag
                        key={tag}
                        closable
                        color={tagColors[tag]}
                        onClose={() => handleTagClose(tag)}
                        style={{ marginBottom: 8, marginRight: 8 }}
                      >
                        {tag}
                      </Tag>
                    ))}
                  </div>
                  <Input
                    value={inputValue}
                    onChange={handleInputChange}
                    onKeyDown={handleInputKeyDown}
                    placeholder={t('common.enterTags')}
                    onClick={(e) => e.stopPropagation()}
                  />
                </div>
              </>
            )}
          </Modal>
        </>
      )}
    </>
  );
};

export default OperateDropdown;
