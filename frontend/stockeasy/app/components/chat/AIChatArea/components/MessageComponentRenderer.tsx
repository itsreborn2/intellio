/**
 * MessageComponentRenderer.tsx
 * 구조화된 메시지 컴포넌트를 렌더링하는 컴포넌트
 */
'use client';

import React from 'react';
import { MessageComponent } from '../types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface MessageComponentRendererProps {
  component: MessageComponent;
}

export function MessageComponentRenderer({ component }: MessageComponentRendererProps) {
  // 컴포넌트 타입에 따라 다른 렌더링 로직 적용
  switch (component.type) {
    case 'heading': {
      const { level, content } = component as any;
      // 헤딩 레벨에 따라 적절한 스타일 적용
      const styles: React.CSSProperties = {
        fontWeight: 'bold',
        lineHeight: 1,
        margin: '0.4em 0 0.2em 0',
        fontSize: level === 1 ? '2em' :
                 level === 2 ? '1.75em' :
                 level === 3 ? '1.45em' :
                 level === 4 ? '1.25em' :
                 level === 5 ? '1.1em' : '1em'
      };
      
      return <div style={styles}>{content}</div>;
    }
    
    case 'paragraph': {
      const { content } = component as any;
      return (
        <div style={{  
                    fontSize: '1.1em',
                    paddingLeft: '0.5em',
                   }}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkBreaks]}
          >
            {content}
          </ReactMarkdown>
        </div>
      );
    }
    
    case 'list': {
      const { ordered, items } = component as any;
      
      if (ordered) {
        return (
          <ol style={{ paddingLeft: '1.5em', margin: '0.5em 0',fontSize: '1.1em' }}>
            {items.map((item: any, index: number) => (
              <li key={index} style={{ margin: '0.25em 0' }}>
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                  {item.content}
                </ReactMarkdown>
              </li>
            ))}
          </ol>
        );
      }
      
      return (
        <ul style={{ listStyleType: 'none', paddingLeft: '1.5em', margin: '0.25em 0',fontSize: '1.1em' }}>
          {items.map((item: any, index: number) => (
            <li key={index} style={{ 
              margin: '0.15em 0',
              position: 'relative',
              paddingLeft: '1.2em'
            }}>
              <span style={{
                position: 'absolute',
                left: '0',
                top: '0',
                fontWeight: 'bold',
              }}>•</span>
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                {item.content}
              </ReactMarkdown>
            </li>
          ))}
        </ul>
      );
    }
    
    case 'code_block': {
      const { language, content } = component as any;
      return (
        <div style={{ margin: '1em 0' }}>
          <pre style={{ 
            padding: '1em', 
            backgroundColor: '#f5f5f5', 
            borderRadius: '5px',
            overflow: 'auto',
            fontSize: '0.9em',
            fontFamily: 'monospace' 
          }}>
            <code className={language ? `language-${language}` : ''}>
              {content}
            </code>
          </pre>
        </div>
      );
    }
    
    case 'bar_chart': {
      const { title, data } = component as any;
      
      return (
        <div style={{ margin: '1em 0', width: '100%' }}>
          {title && <div style={{ fontWeight: 'bold', marginBottom: '0.5em' }}>{title}</div>}
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.labels.map((label: string, index: number) => {
              const dataPoint: Record<string, any> = { name: label };
              
              // 각 데이터셋의 해당 인덱스 값을 추가
              data.datasets.forEach((dataset: any) => {
                dataPoint[dataset.label] = dataset.data[index];
              });
              
              return dataPoint;
            })}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              {data.datasets.map((dataset: any, index: number) => (
                <Bar 
                  key={index} 
                  dataKey={dataset.label} 
                  fill={dataset.backgroundColor || `#${Math.floor(Math.random()*16777215).toString(16)}`} 
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      );
    }
    
    case 'line_chart': {
      const { title, data } = component as any;
      
      return (
        <div style={{ margin: '1em 0', width: '100%' }}>
          {title && <div style={{ fontWeight: 'bold', marginBottom: '0.5em' }}>{title}</div>}
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.labels.map((label: string, index: number) => {
              const dataPoint: Record<string, any> = { name: label };
              
              // 각 데이터셋의 해당 인덱스 값을 추가
              data.datasets.forEach((dataset: any) => {
                dataPoint[dataset.label] = dataset.data[index];
              });
              
              return dataPoint;
            })}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              {data.datasets.map((dataset: any, index: number) => (
                <Line 
                  key={index} 
                  type="monotone" 
                  dataKey={dataset.label} 
                  stroke={dataset.borderColor || `#${Math.floor(Math.random()*16777215).toString(16)}`} 
                  activeDot={{ r: 8 }} 
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      );
    }
    
    case 'table': {
      const { title, data } = component as any;
      
      return (
        <div style={{ margin: '1em 0', width: '100%', overflowX: 'auto' }}>
          {title && <div style={{ fontWeight: 'bold', marginBottom: '0.5em', paddingLeft: '0.3em' }}>{title}</div>}
          <table style={{ 
            width: '100%', 
            borderCollapse: 'collapse',
            fontSize: '0.9em'
          }}>
            <thead>
              <tr>
                {data.headers.map((header: any, index: number) => (
                  <th 
                    key={index} 
                    style={{ 
                      padding: '0.5em', 
                      borderBottom: '2px solid #ddd',
                      textAlign: 'left',
                      fontWeight: 'bold'
                    }}
                  >
                    {header.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row: any, rowIndex: number) => (
                <tr key={rowIndex}>
                  {data.headers.map((header: any, colIndex: number) => (
                    <td 
                      key={colIndex} 
                      style={{ 
                        padding: '0.5em', 
                        borderBottom: '1px solid #ddd'
                      }}
                    >
                      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                        {row[header.key]}
                      </ReactMarkdown>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    
    case 'image': {
      const { url, alt, caption } = component as any;
      
      return (
        <div style={{ margin: '1em 0', width: '100%', textAlign: 'center' }}>
          <img 
            src={url} 
            alt={alt || '이미지'} 
            style={{ 
              maxWidth: '100%', 
              height: 'auto', 
              borderRadius: '4px'
            }} 
          />
          {caption && (
            <div style={{ 
              marginTop: '0.5em', 
              fontSize: '0.9em', 
              color: '#666'
            }}>
              {caption}
            </div>
          )}
        </div>
      );
    }
    
    default:
      // 알 수 없는 컴포넌트 타입일 경우 기본 텍스트로 표시
      return <div>지원되지 않는 컴포넌트 타입: {(component as any).type}</div>;
  }
}

// default export 추가
export default MessageComponentRenderer; 