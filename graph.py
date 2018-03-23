'Graphs'

import collections.abc
import subprocess
import random as _random


# pylint: disable=protected-access


class Link(frozenset):
    'An undirected link'

    def __init__(self, *args):
        if len(args) == 1:
            self.left, self.right = args[0]
        else:
            self.left, self.right = args
        super().__init__()

    def __new__(cls, *args):
        if len(args) == 1:
            pair = set(args[0])
        else:
            pair = set(args)
        if len(pair) != 2:
            raise TypeError('Link expected two arguments or a pair')
        return super().__new__(cls, pair)

    def __iter__(self):
        return iter((self.left, self.right))

    def __repr__(self):
        return '(%r, %r)' % (self.left, self.right)


class LinksView(collections.abc.MutableSet):
    'View of the links of a graph'

    def __init__(self, graph):
        self.graph = graph

    def __iter__(self):
        return iter(self.graph._links)

    def __len__(self):
        return len(self.graph._links)

    def __contains__(self, link):
        try:
            return Link(link) in self.graph._links
        except TypeError:
            return False

    def add(self, value):
        self.graph.add_link(value)

    def discard(self, value):
        self.graph.discard_link(value)

    def __repr__(self):
        return repr(self.graph._links)


class NodeLinksView(collections.abc.MutableSet):
    'View of all links to/from a particular node'

    def __init__(self, graph, node):
        self.graph = graph
        self.node = node

    @property
    def _link_set(self):
        return self.graph._node_links.get(self.node, set())

    def __iter__(self):
        return iter(self._link_set)

    def __len__(self):
        return len(self._link_set)

    def __contains__(self, link):
        return Link(link) in self._link_set

    def add(self, value):
        link = Link(value)
        if not {self.node} <= link:
            raise ValueError('Expected link to node %r' % self.node)
        self.graph.add_link(link)

    def discard(self, value):
        link = Link(value)
        if link not in self._link_set:
            return
        self.graph.discard_link(link)

    def __repr__(self):
        return repr(self._link_set)


class NeighborhoodView(collections.abc.MutableSet):
    'View of the neighborhood of a node'

    def __init__(self, graph, node):
        self.graph = graph
        self.node = node

    @property
    def _neighborhood(self):
        return self.graph._neighborhoods.get(self.node, set())

    def __iter__(self):
        return iter(self._neighborhood)

    def __len__(self):
        return len(self._neighborhood)

    def __contains__(self, neighbor):
        return neighbor in self._neighborhood

    def add(self, value):
        self.graph.add(value)
        if self.node == value:
            return
        self.graph.add_link(Link(self.node, value))

    def discard(self, value):
        if self.node == value:
            raise ValueError('Cannot remove node from its own neighborhood')
        self.graph.discard_link(Link(self.node, value))

    def __repr__(self):
        return repr(self._neighborhood)


class NodeView:
    'View of a particular node in the graph'

    def __init__(self, graph, node):
        self.graph = graph
        self.node = node

    def __bool__(self):
        return self.node in self.graph

    def _get_links(self):
        return NodeLinksView(self.graph, self.node)

    def _set_links(self, links):
        if not self:
            return
        self.links.clear()
        for link in links:
            self.graph.add_link(link)

    def _get_neighborhood(self):
        return NeighborhoodView(self.graph, self.node)

    def _set_neighborhood(self, neighbors):
        if not self:
            return
        neighbors = set(neighbors)
        if self.node not in neighbors:
            raise ValueError('tried to remove node from its own neighborhood')
        self.links.clear()
        for node in neighbors:
            if node == self.node:
                continue
            self.graph.add_link(Link(self.node, node))

    links = property(_get_links, _set_links)
    neighborhood = property(_get_neighborhood, _set_neighborhood)

    def remove_self(self):
        'Remove this node from the graph'
        self.graph.discard(self.node)

    def add_self(self):
        'Add this node to the graph'
        self.graph.add(self.node)

    def link_node(self, other):
        'Add a link from this node to the other'
        self.graph.add_link(Link(self.node, other))

    def unlink_node(self, other):
        'Remove a link from this node to the other'
        self.graph.discard_link(Link(self.node, other))

    def __repr__(self):
        return '<Node view of %r on %r>' % (self.node, self.graph)


class Graph(collections.abc.MutableSet):
    'A set of nodes and links'

    def __init__(self, nodes=(), links=()):
        if isinstance(nodes, Graph):
            self._nodes = set(nodes._nodes)
            self._links = set(nodes._links)
            self._node_links = {node: set(links)
                                for node, links in nodes._node_links.items()}
            self._neighborhoods = {node: set(near)
                                   for node, near in
                                   nodes._neighborhoods.items()}
            return

        self._nodes = set()
        self._links = set()
        self._node_links = {}
        self._neighborhoods = {}
        self |= nodes
        for link in links:
            self.add_link(link)

    def _set_links(self, links):
        self.links.clear()
        for link in links:
            self.links.add(link)

    links = property(LinksView, _set_links)

    def __iter__(self):
        return iter(self._nodes)

    def __len__(self):
        return len(self._nodes)

    def __contains__(self, node):
        return node in self._nodes

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__)
        if not self._links:
            return '%s(%r)' % (self.__class__.__name__, self._nodes)
        return '%s(%r, %r)' % (self.__class__.__name__,
                               self._nodes,
                               self._links)

    def add(self, value):
        self._nodes.add(value)
        self._neighborhoods[value] = {value}

    def discard(self, value):
        for link in tuple(self._node_links.get(value, ())):
            self.discard_link(link)
        self._nodes.discard(value)
        del self._neighborhoods[value]

    def add_link(self, link):
        'Add a link to the graph'
        link = Link(link)
        for node in link:
            if node not in self:
                raise ValueError('Cannot link to missing node %r' % node)
        self._node_links.setdefault(link.left, set()).add(link)
        self._node_links.setdefault(link.right, set()).add(link)
        self._neighborhoods[link.left].add(link.right)
        self._neighborhoods[link.right].add(link.left)
        self._links.add(link)

    def discard_link(self, link):
        'Remove a link from the graph'
        link = Link(link)
        _discard_and_del(self._node_links, link.left, link)
        _discard_and_del(self._node_links, link.right, link)
        self._neighborhoods[link.left].discard(link.right)
        self._neighborhoods[link.right].discard(link.left)
        self._links.discard(link)

    def node_links(self, node):
        'Get the links of a particular node'
        return NodeLinksView(self, node)

    def neighborhood(self, node):
        'Get the neighborhood of a node'
        return NeighborhoodView(self, node)

    def node_view(self, node):
        'Construct a node view object'
        return NodeView(self, node)

    def relabeled(self, *args, **kwargs):
        'Relabel the graph using the provided mapping'
        graph = Graph()
        mapping = dict(*args, **kwargs)
        labels = set(mapping)
        if labels != self or labels != set(mapping.values()):
            raise ValueError('expected a one-to-one onto label mapping')
        for node in self:
            graph.add(mapping[node])
        for left, right in self.links:
            graph.add_link(Link(mapping[left], mapping[right]))
        return graph

    def shuffled(self, random=_random.random):
        'Shuffle the graph labels'
        keys = list(self)
        values = list(keys)
        _random.shuffle(values, random)
        return self.relabeled(zip(keys, values))

    def minimal_spanning(self, node):
        'Compute the minimal spanning subgraph starting at node'
        return MinimalSpanningSubgraph(self, node)

    def minimal_spanning_forrest(self):
        'Compute the minimal spanning subgraph forrest'
        return {node: self.minimal_spanning(node) for node in self}

    def render_graph(self, **kwargs):
        'Render the graph into the graphviz language'
        lines = []
        name = _dot_escape(kwargs.get('graph_name') or '')
        lines.append('graph ' + name + ' {')
        lines.append(_dot_style(kwargs.get('graph_style'), ';\n'))
        lines += self.render_nodes_and_links(**kwargs)
        lines.append('}')
        lines.append('')
        return '\n'.join(lines)

    def render_nodes_and_links(self, **kwargs):
        'Render all nodes and return a list of lines'
        lines = []
        for node in self:
            lines.append(self.render_node(node, **kwargs))
        for link in self.links:
            lines.append(self.render_link(link, **kwargs))
        return lines

    def render_node(self, node, **kwargs): # pylint: disable=no-self-use
        'Render a node in the graphviz format'
        node_styles = kwargs.get('node_styles', {})
        return '%s [%s];' % (_dot_escape(node),
                             _dot_style(node_styles.get(node), ', '))

    def render_link(self, link, **kwargs): # pylint: disable=no-self-use
        'Render a link in the graphviz format'
        link_styles = kwargs.get('link_styles', {})
        return '%s -- %s [%s];' % (_dot_escape(link.left),
                                   _dot_escape(link.right),
                                   _dot_style(link_styles.get(link), ', '))

    def save_dot(self, file, **kwargs):
        'Save the graph to a file in the graphviz format'
        do_close = False
        if isinstance(file, str):
            file = open(file, 'wb')
            do_close = True
        file.write(self.render_graph(**kwargs).encode('utf8'))
        file.flush()
        if do_close:
            file.close()

    def display(self, **kwargs):
        'Display the graph using graphviz'
        graphviz_args = list(kwargs.get('graphviz_args', ['-Tx11']))
        graphviz_args.insert(0, kwargs.get('graphviz_exec', 'dot'))
        sub = subprocess.Popen(graphviz_args, stdin=subprocess.PIPE)
        sub.stdin.write(self.render_graph(**kwargs).encode('utf8'))
        sub.stdin.close()


def _discard_and_del(mapping, key, elem):
    collection = mapping.get(key, set())
    collection.discard(elem)
    if not collection:
        mapping.pop(key, None)


def _dot_style(style, delimiter):
    if not style:
        return ''
    if isinstance(style, str):
        return style
    clauses = []
    for key, value in style.items():
        clauses.append(_dot_escape(key) + '=' + _dot_escape(value) + delimiter)
    return ''.join(clauses)


def _dot_escape(string):
    escape = getattr(string, '_dot_escape', None)
    if escape:
        return escape()
    string = str(string)
    return '"' + string.replace('\\', '\\\\').replace('"', '\\"') + '"'


def complete_graph(nodes):
    'Construct the complete graph on the set of nodes'
    if isinstance(nodes, int):
        nodes = range(nodes)
    graph = Graph(nodes)
    for i in graph:
        for j in graph:
            if i != j:
                graph.add_link(Link(i, j))
    return graph


def erdos_renyi(nodes, *, links=None, link_chance=0.5, random=_random.random):
    'Random graph'
    if isinstance(nodes, int):
        nodes = range(nodes)
    graph = Graph(nodes)
    if links is not None:
        link_set = [(i, j) for i in graph for j in graph if i != j]
        _random.shuffle(link_set, random)
        for link in link_set[:links]:
            graph.add_link(link)
    else:
        for left in graph:
            for right in graph:
                if left == right:
                    continue
                if random() < link_chance:
                    graph.add_link(Link(left, right))
    return graph


class MinimalSpanningSubgraph(Graph):
    'The minimal spanning subgraph rooted at the start node'

    def __init__(self, graph, start):
        sub, layers = _minimal_spanning_subgraph(graph, start)
        self.layers = tuple(layers)
        self.start = start
        super().__init__(sub)

    def add(self, value):
        raise TypeError('Minimal spanning graphs are immutable')

    def discard(self, value):
        raise TypeError('Minimal spanning graphs are immutable')

    def add_link(self, link):
        raise TypeError('Minimal spanning graphs are immutable')

    def discard_link(self, link):
        raise TypeError('Minimal spanning graphs are immutable')

    def render_graph(self, **kwargs):
        kwargs.setdefault('graphviz_exec', 'dot')
        graph_style = kwargs.setdefault('graph_style', {})
        graph_style.setdefault('rankdir', 'TB')
        graph_style.setdefault('newrank', 'false')
        kwargs.setdefault('node_styles', {}) \
              .setdefault(self.start, {}) \
              .setdefault('color', 'red')
        kwargs.setdefault('layers', self.layers)
        return super().render_graph(**kwargs)

    def render_nodes_and_links(self, **kwargs):
        lines = []
        for layer in self.layers:
            lines.append('{')
            lines.append('rank=same;')
            for node in layer:
                lines.append(self.render_node(node, **kwargs))
            lines.append('}')
        seen = set()
        for layer in self.layers:
            lines.append('{')
            for node in layer:
                seen.add(node)
                for child in self.neighborhood(node):
                    if child in seen:
                        continue
                    lines.append(self.render_link(Link(node, child), **kwargs))
            lines.append('}')
        return lines


def _minimal_spanning_subgraph(graph, start):
    'Compute the minimal spanning subgraph'
    layers = []
    subgraph = Graph()
    seen = set()
    level = None
    next_level = set()

    if start in graph:
        subgraph.add(start)
        next_level.add(start)

    while next_level:
        level, next_level = next_level, set()
        seen |= level
        layers.append(level)
        for parent in level:
            for child in graph.neighborhood(parent):
                if child in seen:
                    continue
                subgraph.add(child)
                subgraph.add_link(Link(parent, child))
                next_level.add(child)
    return subgraph, layers
