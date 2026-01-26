/**
 * A2UI Primitives Registry
 *
 * This file exports all available A2UI primitives that the agent can use
 * to compose dynamic user interfaces.
 *
 * Implements the A2UI Standard Catalog (v0.8):
 * https://github.com/google/A2UI/blob/main/specification/0.8/json/standard_catalog_definition.json
 *
 * @see docs/A2UI_IMPLEMENTATION.md for full specification
 */

// Layout Primitives
import { Card } from './Card';
import { Row } from './Row';
import { Column } from './Column';
import { Grid } from './Grid';
import { Divider } from './Divider';
import { Tabs } from './Tabs';
import { Modal } from './Modal';

// Content Primitives
import { Text } from './Text';
import { Image } from './Image';
import { Icon } from './Icon';
import { Badge } from './Badge';
import { Video } from './Video';
import { AudioPlayer } from './AudioPlayer';

// Interactive Primitives
import { Button } from './Button';
import { TextField } from './TextField';
import { Select } from './Select';
import { Checkbox } from './Checkbox';
import { DateTimeInput } from './DateTimeInput';
import { MultipleChoice } from './MultipleChoice';
import { Slider } from './Slider';

// Collection Primitives
import { DataTable } from './DataTable';
import { List } from './List';

// Re-export all primitives
export {
  // Layout
  Card,
  Row,
  Column,
  Grid,
  Divider,
  Tabs,
  Modal,
  // Content
  Text,
  Image,
  Icon,
  Badge,
  Video,
  AudioPlayer,
  // Interactive
  Button,
  TextField,
  Select,
  Checkbox,
  DateTimeInput,
  MultipleChoice,
  Slider,
  // Collections
  DataTable,
  List,
};

/**
 * Registry of all A2UI primitives
 * Used by A2UIRenderer to look up components by type
 *
 * Standard A2UI (v0.8): Text, Image, Icon, Video, AudioPlayer, Row, Column,
 *                       List, Card, Tabs, Divider, Modal, Button, CheckBox,
 *                       TextField, DateTimeInput, MultipleChoice, Slider
 *
 * Extensions: Grid, Badge, Select, DataTable
 */
export const A2UI_PRIMITIVES = {
  // Layout
  Card,
  Row,
  Column,
  Grid,
  Divider,
  Tabs,
  Modal,

  // Content
  Text,
  Image,
  Icon,
  Badge,
  Video,
  AudioPlayer,

  // Interactive
  Button,
  TextField,
  Select,
  Checkbox,
  DateTimeInput,
  MultipleChoice,
  Slider,

  // Collections
  DataTable,
  List,
};
