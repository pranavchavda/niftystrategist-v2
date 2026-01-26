/**
 * A2UI Context - Data model and state management for A2UI surfaces
 *
 * Implements A2UI v0.8 specification data binding:
 * - literalString/literalNumber/literalArray: Static values
 * - path: Dynamic binding to data model (e.g., "/user/name")
 *
 * @see https://a2ui.org/specification/v0.8-a2ui/
 */

import { createContext, useContext, useState, useCallback, useMemo } from 'react';

// Context for A2UI data model
const A2UIDataContext = createContext({
  dataModel: {},
  updateDataModel: () => {},
  resolveValue: () => null,
  formState: {},
  updateFormState: () => {},
});

/**
 * Resolve a path like "/user/name" from the data model
 */
function resolvePath(dataModel, path) {
  if (!path || typeof path !== 'string') return undefined;

  // Remove leading slash and split
  const parts = path.replace(/^\//, '').split('/');

  let current = dataModel;
  for (const part of parts) {
    if (current === undefined || current === null) return undefined;
    current = current[part];
  }

  return current;
}

/**
 * Set a value at a path in the data model
 */
function setAtPath(dataModel, path, value) {
  if (!path || typeof path !== 'string') return dataModel;

  const parts = path.replace(/^\//, '').split('/');
  const newModel = { ...dataModel };

  let current = newModel;
  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    if (current[part] === undefined) {
      current[part] = {};
    } else {
      current[part] = { ...current[part] };
    }
    current = current[part];
  }

  current[parts[parts.length - 1]] = value;
  return newModel;
}

/**
 * Resolve an A2UI value object to its actual value
 *
 * A2UI values can be:
 * - { literalString: "hello" }
 * - { literalNumber: 42 }
 * - { literalArray: ["a", "b"] }
 * - { path: "/user/name" }
 * - { path: "/user/name", literalString: "default" } (initialization)
 * - Direct value (for backwards compatibility)
 */
export function resolveA2UIValue(valueObj, dataModel = {}) {
  // Direct value (backwards compatibility)
  if (valueObj === null || valueObj === undefined) return valueObj;
  if (typeof valueObj !== 'object') return valueObj;
  if (Array.isArray(valueObj)) return valueObj;

  // A2UI spec format
  if ('literalString' in valueObj) return valueObj.literalString;
  if ('literalNumber' in valueObj) return valueObj.literalNumber;
  if ('literalArray' in valueObj) return valueObj.literalArray;
  if ('literalBoolean' in valueObj) return valueObj.literalBoolean;

  // Path binding
  if ('path' in valueObj) {
    const resolved = resolvePath(dataModel, valueObj.path);
    // If path resolves to undefined, use literal as fallback/initialization
    if (resolved === undefined) {
      if ('literalString' in valueObj) return valueObj.literalString;
      if ('literalNumber' in valueObj) return valueObj.literalNumber;
      if ('literalArray' in valueObj) return valueObj.literalArray;
    }
    return resolved;
  }

  // Not a value object, return as-is (might be a nested component)
  return valueObj;
}

/**
 * A2UI Data Provider - Wraps a surface with data model context
 */
export function A2UIDataProvider({ children, initialData = {} }) {
  const [dataModel, setDataModel] = useState(initialData);
  const [formState, setFormState] = useState({});

  const updateDataModel = useCallback((pathOrUpdates, value) => {
    if (typeof pathOrUpdates === 'string') {
      // Single path update
      setDataModel(prev => setAtPath(prev, pathOrUpdates, value));
    } else if (typeof pathOrUpdates === 'object') {
      // Batch update (from dataModelUpdate message)
      setDataModel(prev => ({ ...prev, ...pathOrUpdates }));
    }
  }, []);

  const resolveValue = useCallback((valueObj) => {
    return resolveA2UIValue(valueObj, dataModel);
  }, [dataModel]);

  const updateFormState = useCallback((fieldName, value) => {
    setFormState(prev => ({ ...prev, [fieldName]: value }));
  }, []);

  const contextValue = useMemo(() => ({
    dataModel,
    updateDataModel,
    resolveValue,
    formState,
    updateFormState,
  }), [dataModel, updateDataModel, resolveValue, formState, updateFormState]);

  return (
    <A2UIDataContext.Provider value={contextValue}>
      {children}
    </A2UIDataContext.Provider>
  );
}

/**
 * Hook to access A2UI data context
 */
export function useA2UIData() {
  return useContext(A2UIDataContext);
}

/**
 * Hook to resolve a value with data binding
 */
export function useA2UIValue(valueObj) {
  const { resolveValue } = useA2UIData();
  return resolveValue(valueObj);
}

export { A2UIDataContext };
