import { formatDate } from '@/utils/date';
import { CalendarOutlined, DownOutlined, UpOutlined } from '@ant-design/icons';
import { Button, Card, Tag, Typography } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'umi';

import OperateDropdown from '@/components/operate-dropdown';
import conf from '@/conf.json';
import { useDeleteFlow, useFetchAgentInfo } from '@/hooks/flow-hooks';
import { IFlow } from '@/interfaces/database/flow';
import { useCallback } from 'react';
import GraphAvatar from '../graph-avatar';
import styles from './index.less';

interface IProps {
  item: IFlow;
  onPermissionChange?: (permission: string) => void;
}

const FlowCard = ({ item, onPermissionChange }: IProps) => {
  const navigate = useNavigate();
  const { deleteFlow } = useDeleteFlow();
  const { data: agentInfo } = useFetchAgentInfo(item.id);
  const prevPermissionRef = useRef<string>();
  const [isTagsExpanded, setIsTagsExpanded] = useState(false);
  const tagsContainerRef = useRef<HTMLDivElement>(null);

  // 当权限信息变化时通知父组件
  useEffect(() => {
    if (
      agentInfo?.permission &&
      onPermissionChange &&
      agentInfo.permission !== prevPermissionRef.current
    ) {
      prevPermissionRef.current = agentInfo.permission;
      onPermissionChange(agentInfo.permission);
    }
  }, [agentInfo?.permission]);

  // 获取行业标签
  const getIndustryLabel = (value: string) => {
    const option = conf.industryOptions.find((opt) => opt.value === value);
    return option?.label || '';
  };

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

  // 为每个标签分配一个颜色
  const tagColors =
    agentInfo?.tags?.reduce(
      (acc: { [key: string]: string }, tag: string) => {
        acc[tag] = colors[Math.floor(Math.random() * colors.length)];
        return acc;
      },
      {} as { [key: string]: string },
    ) || {};

  const removeFlow = useCallback(() => {
    return deleteFlow([item.id]);
  }, [deleteFlow, item]);

  const handleCardClick = () => {
    navigate(`/flow/${item.id}`);
  };

  // 检查是否需要显示展开按钮
  const shouldShowExpandButton = () => {
    if (!tagsContainerRef.current) return false;
    const container = tagsContainerRef.current;
    // 获取实际内容高度
    const contentHeight = container.scrollHeight;
    // 获取容器高度（两行）
    const containerHeight = 64; // 64px = 2行的高度
    // 只有当内容高度超过容器高度时才显示展开按钮
    return contentHeight > containerHeight;
  };

  return (
    <Card className={styles.card} onClick={handleCardClick}>
      <div className={styles.container}>
        <div className={styles.content}>
          <GraphAvatar avatar={item.avatar} />
          <OperateDropdown deleteItem={removeFlow} agentId={item.id} />
        </div>
        <div className={styles.titleWrapper}>
          <Typography.Title
            className={styles.title}
            ellipsis={{ tooltip: item.title }}
          >
            {item.title}
          </Typography.Title>
          <p>{item.description}</p>
          {/* 行业标识 */}
          {agentInfo?.canvas_industry && (
            <div style={{ marginBottom: 8 }}>
              <Tag
                style={{
                  background: '#1677ff',
                  color: 'white',
                  border: 'none',
                  padding: '2px 8px',
                  borderRadius: '6px',
                  fontSize: '14px',
                  fontWeight: 400,
                }}
              >
                {getIndustryLabel(agentInfo.canvas_industry)}
              </Tag>
            </div>
          )}
          {/* 标签展示区域 */}
          <div
            ref={tagsContainerRef}
            className={styles.tags}
            style={{
              maxHeight: isTagsExpanded ? 'none' : '64px',
              overflow: 'hidden',
              position: 'relative',
              paddingBottom: shouldShowExpandButton() ? '28px' : '0', // 增加padding确保按钮不会遮挡标签
            }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {agentInfo?.tags?.map((tag: string) => (
                <Tag key={tag} color={tagColors[tag]} style={{ margin: 0 }}>
                  {tag}
                </Tag>
              ))}
            </div>
            {shouldShowExpandButton() && (
              <Button
                type="text"
                size="small"
                icon={isTagsExpanded ? <UpOutlined /> : <DownOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  setIsTagsExpanded(!isTagsExpanded);
                }}
                style={{
                  padding: '0 4px',
                  height: '24px',
                  position: 'absolute',
                  bottom: 0,
                  right: 0,
                  background: 'white',
                  zIndex: 1,
                  boxShadow: '0 -2px 4px rgba(0,0,0,0.05)', // 添加阴影效果
                }}
              >
                {isTagsExpanded ? '' : ''}
              </Button>
            )}
          </div>
        </div>
        <div className={styles.footer}>
          <div className={styles.bottom}>
            <div className={styles.bottomLeft}>
              <CalendarOutlined className={styles.leftIcon} />
              <span className={styles.rightText}>
                {formatDate(item.update_time)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default FlowCard;
