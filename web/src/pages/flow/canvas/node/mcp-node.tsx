import { useTheme } from '@/components/theme-provider';
import { IMCPNode } from '@/interfaces/database/flow';
import { Handle, NodeProps, Position } from '@xyflow/react';
import classNames from 'classnames';
import { LeftHandleStyle, RightHandleStyle } from './handle-icon';
import styles from './index.less';
import NodeHeader from './node-header';

export function MCPNode({
  id,
  data,
  isConnectable = true,
  selected,
}: NodeProps<IMCPNode>) {
  const { theme } = useTheme();
  return (
    <section
      className={classNames(
        styles.logicNode,
        theme === 'dark' ? styles.dark : '',
        {
          [styles.selectedNode]: selected,
        },
      )}
    >
      <Handle
        id="c"
        type="source"
        position={Position.Left}
        isConnectable={isConnectable}
        className={styles.handle}
        style={LeftHandleStyle}
      ></Handle>
      <Handle
        type="source"
        position={Position.Right}
        isConnectable={isConnectable}
        className={styles.handle}
        style={RightHandleStyle}
        id="b"
      ></Handle>

      <NodeHeader
        id={id}
        name={data.name}
        label={data.label}
        className={styles.nodeHeader}
      ></NodeHeader>
    </section>
  );
}
