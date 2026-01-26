/**
 * A2UIRenderer - Renders A2UI surfaces per v0.8 specification
 *
 * Supports both A2UI spec format and simplified format for backwards compatibility:
 *
 * Spec format (adjacency list):
 * {
 *   id: "text-1",
 *   component: { Text: { text: { literalString: "Hello" } } }
 * }
 *
 * Simplified format (backwards compatible):
 * {
 *   id: "text-1",
 *   type: "Text",
 *   text: "Hello"
 * }
 *
 * @see https://a2ui.org/specification/v0.8-a2ui/
 * @see docs/A2UI_IMPLEMENTATION.md
 */

import { useState, useCallback, useMemo } from 'react';
import { A2UI_PRIMITIVES } from './primitives';
import { A2UIDataProvider, useA2UIData, resolveA2UIValue } from './A2UIContext';

// Create case-insensitive lookup map
const PRIMITIVE_LOOKUP = {};
Object.keys(A2UI_PRIMITIVES).forEach(key => {
  PRIMITIVE_LOOKUP[key.toLowerCase()] = A2UI_PRIMITIVES[key];
});

// Map common HTML/alternative names to our primitives
const TYPE_ALIASES = {
  'div': 'column',
  'span': 'text',
  'heading': 'text',
  'h1': 'text',
  'h2': 'text',
  'h3': 'text',
  'h4': 'text',
  'h5': 'text',
  'h6': 'text',
  'p': 'text',
  'img': 'image',
  'ul': 'list',
  'table': 'datatable',
  'input': 'textfield',
  'label': 'text',
  'container': 'card',
  'box': 'card',
  'hstack': 'row',
  'vstack': 'column',
  // A2UI spec aliases
  'checkbox': 'checkbox',
  'audioplayer': 'audioplayer',
  'datetimeinput': 'datetimeinput',
  'multiplechoice': 'multiplechoice',
};

/**
 * Normalize a component definition to a standard internal format
 *
 * Handles both A2UI spec format and simplified format
 */
function normalizeComponent(component, dataModel = {}) {
  if (!component) return null;

  // Spec format: { id: "x", component: { Text: { text: {...} } } }
  if (component.component && typeof component.component === 'object') {
    const componentType = Object.keys(component.component)[0];
    const componentProps = component.component[componentType] || {};

    // Resolve all prop values
    const resolvedProps = {};
    for (const [key, value] of Object.entries(componentProps)) {
      if (key === 'children') {
        // Children handled separately
        resolvedProps[key] = value;
      } else {
        resolvedProps[key] = resolveA2UIValue(value, dataModel);
      }
    }

    return {
      id: component.id,
      type: componentType,
      props: resolvedProps,
      children: componentProps.children,
    };
  }

  // Simplified format: { id: "x", type: "Text", text: "Hello" }
  // Also supports "components" as alias for "children" (common agent pattern)
  if (component.type) {
    const { type, id, props, children, components, ...directProps } = component;

    // Resolve direct props that might be in A2UI value format
    const resolvedProps = {};
    const propsToResolve = { ...directProps, ...props };
    for (const [key, value] of Object.entries(propsToResolve)) {
      if (key === 'children' || key === 'components') continue;
      resolvedProps[key] = resolveA2UIValue(value, dataModel);
    }

    return {
      id,
      type,
      props: resolvedProps,
      children: children || components,  // Support both "children" and "components"
    };
  }

  console.warn('[A2UI] Unknown component format:', component);
  return null;
}

/**
 * Resolve children from A2UI spec format
 *
 * Supports:
 * - explicitList: ["id1", "id2"] - array of component IDs
 * - template: { dataBinding: "/items", componentId: "template" } - dynamic list
 * - Direct array (backwards compatible)
 */
function resolveChildren(childrenSpec, componentMap, dataModel) {
  if (!childrenSpec) return [];

  // Direct array of components (backwards compatible)
  if (Array.isArray(childrenSpec)) {
    return childrenSpec;
  }

  // Spec format: { explicitList: ["id1", "id2"] }
  if (childrenSpec.explicitList) {
    return childrenSpec.explicitList.map(id => componentMap.get(id)).filter(Boolean);
  }

  // Spec format: { template: { dataBinding: "/items", componentId: "template" } }
  if (childrenSpec.template) {
    const { dataBinding, componentId } = childrenSpec.template;
    const items = resolveA2UIValue({ path: dataBinding }, dataModel);
    const templateComponent = componentMap.get(componentId);

    if (!Array.isArray(items) || !templateComponent) {
      return [];
    }

    // Generate components from template
    return items.map((item, index) => ({
      ...templateComponent,
      id: `${componentId}-${index}`,
      // Inject item data into component context
      _templateData: item,
      _templateIndex: index,
    }));
  }

  return [];
}

/**
 * Build component map from flat adjacency list
 */
function buildComponentMap(components) {
  const map = new Map();
  if (!components) return map;

  for (const component of components) {
    if (component.id) {
      map.set(component.id, component);
    }
  }

  return map;
}

/**
 * Inner renderer component that uses the data context
 */
function A2UIRendererInner({ surface, onInteraction, threadId }) {
  const { dataModel, formState, updateFormState } = useA2UIData();

  // Build component map for ID lookups (for explicitList children)
  const componentMap = useMemo(
    () => buildComponentMap(surface.components),
    [surface.components]
  );

  /**
   * Create a userAction event per A2UI spec
   */
  const createUserAction = useCallback((actionName, componentId, context = {}) => {
    return {
      name: actionName,
      surfaceId: surface.surfaceId,
      sourceComponentId: componentId,
      timestamp: new Date().toISOString(),
      context: { ...formState, ...context },
    };
  }, [surface.surfaceId, formState]);

  /**
   * Recursively render a component
   */
  const renderComponent = useCallback((component) => {
    const normalized = normalizeComponent(component, dataModel);
    if (!normalized) return null;

    const { id, type, props, children } = normalized;
    const typeLower = type.toLowerCase();

    // Look up primitive
    let Primitive = PRIMITIVE_LOOKUP[typeLower];
    if (!Primitive && TYPE_ALIASES[typeLower]) {
      Primitive = PRIMITIVE_LOOKUP[TYPE_ALIASES[typeLower]];
    }

    if (!Primitive) {
      console.warn(`[A2UI] Unknown primitive type: ${type}`);
      // Fallback for containers
      const resolvedChildren = resolveChildren(children, componentMap, dataModel);
      if (resolvedChildren.length > 0) {
        return (
          <div key={id} className="a2ui-fallback">
            {resolvedChildren.map(renderComponent)}
          </div>
        );
      }
      return (
        <div key={id} className="p-2 border border-dashed border-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 rounded text-sm">
          {props?.content || props?.text || `Unknown: ${type}`}
        </div>
      );
    }

    // Resolve children
    const resolvedChildren = resolveChildren(children, componentMap, dataModel);

    // Render primitive
    return (
      <Primitive
        key={id}
        id={id}
        {...props}
        onInteraction={(action, payload) => {
          const userAction = createUserAction(action, id, payload);
          onInteraction?.(userAction);
        }}
        onFormChange={updateFormState}
        renderComponent={renderComponent}
      >
        {resolvedChildren.map(renderComponent)}
      </Primitive>
    );
  }, [dataModel, componentMap, createUserAction, onInteraction, updateFormState]);

  // Find root components (those not referenced as children of others)
  const rootComponents = useMemo(() => {
    if (!surface.components) return [];

    // For simplified format, just render all top-level components
    // For spec format with adjacency list, find roots
    const childIds = new Set();
    for (const component of surface.components) {
      const normalized = normalizeComponent(component, dataModel);
      if (normalized?.children) {
        const children = resolveChildren(normalized.children, componentMap, dataModel);
        if (Array.isArray(children)) {
          children.forEach(c => {
            if (c?.id) childIds.add(c.id);
            if (typeof c === 'string') childIds.add(c);
          });
        }
        if (normalized.children.explicitList) {
          normalized.children.explicitList.forEach(id => childIds.add(id));
        }
      }
    }

    // Components that are not children of any other component are roots
    return surface.components.filter(c => !childIds.has(c.id));
  }, [surface.components, componentMap, dataModel]);

  return (
    <div className="a2ui-surface my-3 animate-in fade-in duration-300">
      {surface.title && (
        <div className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-2">
          {surface.title}
        </div>
      )}
      <div className="a2ui-components">
        {rootComponents.map(renderComponent)}
      </div>
    </div>
  );
}

/**
 * Main A2UIRenderer component with data provider wrapper
 */
export default function A2UIRenderer({ surface, onInteraction, threadId, initialData }) {
  return (
    <A2UIDataProvider initialData={initialData || {}}>
      <A2UIRendererInner
        surface={surface}
        onInteraction={onInteraction}
        threadId={threadId}
      />
    </A2UIDataProvider>
  );
}

// Re-export context utilities
export { A2UIDataProvider, useA2UIData, resolveA2UIValue } from './A2UIContext';
