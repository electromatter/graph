import collections.abc
import subprocess
import random as _random


class Link(frozenset):
    def __init__(self, *args):
        self.a, self.b = tuple(self)

    def __new__(cls, *args):
        if len(args) == 1:
            pair = set(args[0])
        else:
            pair = set(args)
        if len(pair) != 2:
            raise TypeError('Link expected two arguments or a pair')
        return super().__new__(cls, pair)

    def __repr__(self):
        return '(%r, %r)' % (self.a, self.b)


class LinksView(collections.abc.MutableSet):
    def __init__(self, graph):
        self.graph = graph

    def __iter__(self):
        return iter(self.graph._links)

    def __len__(self):
        return len(self.graph._links)

    def __contains__(self, *args):
        try:
            return Link(*args) in self.graph._links
        except TypeError:
            return False

    def add(self, *args):
        self.graph.add_link(*args)

    def discard(self, *args):
        self.graph.discard_link(*args)

    def __repr__(self):
        return repr(self.graph._links)


class NodeLinksView(collections.abc.MutableSet):
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

    def __contains__(self, *args):
        try:
            return Link(*args) in self._link_set
        except TypeError:
            return False

    def add(self, *args):
        link = Link(*args)
        if not {self.node} <= link:
            raise ValueError('Expected link to node %r' % self.node)
        self.graph.add_link(link)

    def discard(self, *args):
        link = Link(*args)
        if link not in self._link_set:
            return
        self.graph.discard_link(link)

    def __repr__(self):
        return repr(self._link_set)


class NeighborhoodView(collections.abc.MutableSet):
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

    def add(self, neighbor):
        self.graph.add(neighbor)
        if self.node == neighbor:
            return
        self.graph.add_link((self.node, neighbor))

    def discard(self, neighbor):
        if self.node == neighbor:
            raise ValueError('Cannot remove node from its own neighborhood')
        self.graph.discard_link((self.node, neighbor))

    def __repr__(self):
        return repr(self._neighborhood)


class NodeView:
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
        self.graph.discard(self.node)

    def add_self(self):
        self.graph.add(self.node)

    def link_node(self, other):
        self.graph.add_link(Link(self.node, other))

    def unlink_node(self, other):
        self.graph.discard_link(Link(self.node, other))

    def __repr__(self):
        return '<Node view of %r on %r>' % (self.node, self.graph)


class Graph(collections.abc.MutableSet):
    def __init__(self, nodes=(), links=()):
        self._nodes = set()
        self._links = set()
        self._node_links = {}
        self._neighborhoods = {}
        self |= nodes
        for link in getattr(nodes, 'links', ()):
            self.add_link(link)
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
        return '%s(%r, %r)' % (self.__class__.__name__, \
                               self._nodes,
                               self._links)

    def add(self, node):
        self._nodes.add(node)
        self._neighborhoods[node] = {node}

    def discard(self, node):
        for link in tuple(self._node_links.get(node, ())):
            self.discard_link(link)
        self._nodes.discard(node)
        del self._neighborhoods[node]

    def add_link(self, *args):
        link = Link(*args)
        for node in link:
            if node not in self:
                raise ValueError('Cannot link to missing node %r' % node)
        self._node_links.setdefault(link.a, set()).add(link)
        self._node_links.setdefault(link.b, set()).add(link)
        self._neighborhoods[link.a].add(link.b)
        self._neighborhoods[link.b].add(link.a)
        self._links.add(link)

    def discard_link(self, *args):
        link = Link(*args)
        _discard_and_del(self._node_links, link.a, link)
        _discard_and_del(self._node_links, link.b, link)
        self._neighborhoods[link.a].discard(link.b)
        self._neighborhoods[link.b].discard(link.a)
        self._links.discard(link)

    def link_set(self, node):
        return NodeLinksView(self, node)

    def neighborhood(self, node):
        return NeighborhoodView(self, node)

    def node_view(self, node):
        return NodeView(self, node)

    def relabeled(self, mapping):
        graph = self.__class__()
        mapping = dict(mapping)
        labels = set(mapping)
        if lables != self or labels != set(mapping.values):
            raise ValueError('expected a one-to-one onto label mapping')
        for node in self:
            graph.add(mapping[node])
        for left, right in self.links:
            graph.add_link(Link(mapping[left], mapping[right]))
        return graph

    def render_graph(self, **kwargs):
        lines = []
        name =_dot_escape(kwargs.get('graph_name') or '')
        lines.append('graph ' + name + ' {')
        lines.append(_dot_style(kwargs.get('graph_style'), ';\n'))
        lines += self._render_nodes(**kwargs)
        lines += self._render_links(**kwargs)
        lines.append('}')
        lines.append('')
        return '\n'.join(lines)

    def _render_nodes(self, layers=[], groups={}, group_styles={}, **kwargs):
        lines = []
        seen = set()

        for layer in layers:
            lines.append('{')
            lines.append('rank=same;')
            for node in layer:
                if node in seen:
                    raise ValueError('subgraphs must be disjoint')
                seen.add(node)
                lines.append(self._render_node(node))
            lines.append('}')

        for name, nodes in groups.items():
            lines.append('{')
            lines.append(_dot_style(group_styles.get(name), ';\n'))
            for node in nodes:
                if node in seen:
                    raise ValueError('subgraphs must be disjoint')
                seen.add(node)
                lines.append(self._render_node(node))
            lines.append('}')

        for node in self:
            if node in seen:
                continue
            lines.append(self._render_node(node))

        return lines


    def _render_links(self, **kwargs):
        lines = []
        for link in self.links:
            lines.append(self._render_link(link, **kwargs))
        return lines

    def _render_node(self, node, node_styles={}, **kwargs):
        return '%s [%s];' % (_dot_escape(node), \
                             _dot_style(node_styles.get(node), ', '))

    def _render_link(self, link, link_styles={}, **kwargs):
        return '%s -- %s [%s];' % (_dot_escape(link.a), _dot_escape(link.b), \
                                   _dot_style(link_styles.get(link), ', '))

    def save_dot(self, file, **kwargs):
        do_close = False
        if isinstance(file, str):
            file = open(file, 'w')
            do_close = True
        file.write(self.render_graph(**kwargs).encode('utf8'))
        file.flush()
        if do_close:
            file.close()

    def display(self, **kwargs):
        graphviz_args = list(kwargs.get('graphviz_args', ['-Tx11']))
        graphviz_args.insert(0, kwargs.get('graphviz_exec', 'neato'))
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
    if hasattr(string, '_dot_escape'):
        return string._dot_escape()
    string = str(string)
    return '"' + string.replace('\\', '\\\\').replace('"', '\\"') + '"'


def complete_graph(n):
    graph = Graph(range(n))
    for i in graph:
        for j in graph:
            if i != j:
                graph.add_link(i, j)
    return graph


def erdos_renyi(n, *, m=None, p=0.5, random=_random):
    'Random graph'
    graph = Graph(range(n))
    if m is not None:
        links = [(i, j) for i in range(n) for j in range(n) if i != j]
        _random._shuffle(links, random)
        for link in links[:m]:
            graph.add_link(*link)
    else:
        if p <= 0:
            return graph
        if p >= 1:
            return complete_graph(n)
        for left in range(n):
            for right in range(n):
                if left == right:
                    continue
                if random.random() < p:
                    graph.add_link(Link(left, right))
    return graph


def minimum_spanning_subgraph(graph, start):
    if start not in graph:
        return Graph()
    layers = []
    subgraph = Graph((start,))
    seen = set()
    level = None
    next_level = {start}
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
