import { PlusOutlined } from '@ant-design/icons';
import { Button, Divider, Empty, Flex, Spin } from 'antd';
import { useEffect, useState } from 'react';
import AgentTemplateModal from './agent-template-modal';
import FlowCard from './flow-card';
import { useFetchDataOnMount, useSaveFlow } from './hooks';

import { useTranslate } from '@/hooks/common-hooks';
import styles from './index.less';

const PermissionGroup = ({
  items,
  permission,
  onItemPermissionChange,
}: {
  items: any[];
  permission: string;
  onItemPermissionChange: (itemId: string, newPermission: string) => void;
}) => {
  const permissionText = {
    private: '私有',
    public: '公共',
    team: '团队',
  } as const;

  return (
    <div>
      <div style={{ marginBottom: 16, fontSize: 16, fontWeight: 500 }}>
        {permissionText[permission as keyof typeof permissionText]}
      </div>
      <Flex gap={'large'} wrap="wrap">
        {items.map((item) => (
          <FlowCard
            item={item}
            key={item.id}
            onPermissionChange={(newPermission) =>
              onItemPermissionChange(item.id, newPermission)
            }
          />
        ))}
      </Flex>
    </div>
  );
};

const FlowList = () => {
  const {
    showFlowSettingModal,
    hideFlowSettingModal,
    flowSettingVisible,
    flowSettingLoading,
    onFlowOk,
  } = useSaveFlow();
  const { t } = useTranslate('flow');

  const { list, loading } = useFetchDataOnMount();
  const [groupedList, setGroupedList] = useState<{ [key: string]: any[] }>({});

  useEffect(() => {
    // 初始化分组
    const grouped = list.reduce((acc: { [key: string]: any[] }, item) => {
      const permission = 'private'; // 默认权限
      if (!acc[permission]) {
        acc[permission] = [];
      }
      acc[permission].push(item);
      return acc;
    }, {});
    setGroupedList(grouped);
  }, [list]);

  const handlePermissionChange = (itemId: string, newPermission: string) => {
    setGroupedList((prev) => {
      const newGrouped = { ...prev };

      // 从所有组中移除该项目
      Object.keys(newGrouped).forEach((permission) => {
        newGrouped[permission] = newGrouped[permission].filter(
          (item) => item.id !== itemId,
        );
      });

      // 添加到新权限组
      const item = list.find((i) => i.id === itemId);
      if (item) {
        if (!newGrouped[newPermission]) {
          newGrouped[newPermission] = [];
        }
        newGrouped[newPermission].push(item);
      }

      // 移除空组
      Object.keys(newGrouped).forEach((permission) => {
        if (newGrouped[permission].length === 0) {
          delete newGrouped[permission];
        }
      });

      return newGrouped;
    });
  };

  return (
    <Flex className={styles.flowListWrapper} vertical flex={1} gap={'large'}>
      <Flex justify={'end'}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={showFlowSettingModal}
        >
          {t('createGraph')}
        </Button>
      </Flex>
      <Spin spinning={loading}>
        <Flex vertical gap={'large'} className={styles.flowCardContainer}>
          {Object.entries(groupedList).map(([permission, items], index) => (
            <div key={permission}>
              <PermissionGroup
                items={items}
                permission={permission}
                onItemPermissionChange={handlePermissionChange}
              />
              {index < Object.keys(groupedList).length - 1 && (
                <Divider style={{ margin: '24px 0' }} />
              )}
            </div>
          ))}
          {list.length === 0 && <Empty className={styles.knowledgeEmpty} />}
        </Flex>
      </Spin>
      {flowSettingVisible && (
        <AgentTemplateModal
          visible={flowSettingVisible}
          onOk={onFlowOk}
          loading={flowSettingLoading}
          hideModal={hideFlowSettingModal}
        />
      )}
    </Flex>
  );
};

export default FlowList;
