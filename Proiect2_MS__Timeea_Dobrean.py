import pygame
import random
import math
import matplotlib
import os

# Configurare backend Matplotlib adaptiv: prioritate GUI → fallback headless
_backend_set = False

#  Verifica daca sistemul are server grafic (X11 sau Wayland)
if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
    # Încearca GTK4 (ferestre interactive moderne)
    try:
        import gi
        if hasattr(gi, 'require_version'):
            try:
                gi.require_version("Gtk", "4.0")
                matplotlib.use('GTK4Agg')
                _backend_set = True
            except Exception:
                # GTK4 nu e disponibil, continui la Tkinter
                _backend_set = False
    except Exception:
        # PyGObject nu e instalat
        pass

# Daca GTK4 esueaza, încearca Tkinter (universal, mai simplu)
if not _backend_set:
    try:
        import tkinter as _tk
        matplotlib.use('TkAgg')
        _backend_set = True
    except Exception:
        # Nici Tkinter nu merge
        pass

# Fallback final - backend headless (salvează PNG, fara ferestre)
if not _backend_set:
    matplotlib.use('Agg')


import matplotlib.pyplot as plt


pygame.init()

# Screen dimensions
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600

# Colors
COLOR_BG = (30, 30, 30)
COLOR_PREY = (0, 200, 0)    # Verde pentru prada (prey)
COLOR_PREDATOR = (255, 50, 50)  # Rosu pentru prădător
COLOR_FOOD = (255, 105, 180)      # Roz pentru mâncare
COLOR_OBSTACLE = (0, 122, 204)  # Albastru pentru obstacole
COLOR_TEXT = (255, 255, 255)      # Alb pentru text
COLOR_MATING = (255, 255, 255)    # Alb pentru cautare partener
COLOR_MATING_ACTION = (255, 255, 0) # Galben pentru împerechere

# Reproducere
ENERGY_TO_REPRODUCE = 200 # Valoare de energie necesara pentru reproducere
ENERGY_REPRODUCE_COST = 120      # Costul de energie pentru reproducere
MATING_FRAMES = 50      # Durata în frame-uri a starii de împerechere

# Energie
ENERGY_START = 100
ENERGY_MAX = 600
ENERGY_LOSS_PER_FRAME = 0.1 # Energie pierduta pe frame
ENERGY_FROM_FOOD = 40 # Energie caștigată la consumarea hranei
ENERGY_FROM_PREY = 150 # Energie caștigată la consumarea prăzii
INITIAL_FOOD_COUNT = 80  # Numărul de obiecte de hrană în simulare

# Haita
FLOCK_DETECTION_RADIUS = 80 # Raza pentru detectia celorlalti membri ai haitei
FLOCK_SEPARATION_WEIGHT = 0.85  # Distanța minimă față de alți membri ai haitei
FLOCK_ALIGNMENT_WEIGHT = 1 # Cât de mult să se alinieze cu direcția medie a haitei
FLOCK_COHESION_WEIGHT = 1   # Cât de mult să se apropie de centrul haitei
FLOCK_MAX_NEIGHBORS = 7  # Numărul maxim de vecini luați în considerare pentru haita

# Obstacole
NUM_OBSTACLES = 8
COLOR_OBSTACLE = (0, 122, 204)
OBSTACLE_MIN_RADIUS = 20
OBSTACLE_MAX_RADIUS = 30
OBSTACLE_AVOID_WEIGHT = 3 # Cat de mult să evite obstacolele

# Frame rate and speeds
FRAME_RATE = 60
SPEED_PREY = 1.5
SPEED_PREDATOR = 1.7
# Initialize screen and clock
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Predator-Prey Simulation")
clock = pygame.time.Clock()

# Font for text
FONT = pygame.font.SysFont(None, 24)

class Obstacle:
    """Class representing an obstacle in the simulation."""
    # Initializează obstacolul: rază și poziție aleatoare pe ecran
    def __init__(self):
        self.radius = random.randint(OBSTACLE_MIN_RADIUS, OBSTACLE_MAX_RADIUS)
        self.position = pygame.math.Vector2(random.uniform(self.radius, SCREEN_WIDTH-self.radius), random.uniform(self.radius, SCREEN_HEIGHT-self.radius))

    def draw(self):
        """Draw the obstacle as a gray circle."""
        pygame.draw.circle(screen, COLOR_OBSTACLE, (int(self.position.x), int(self.position.y)), self.radius)

class Food:
    """Class representing food in the simulation."""
    # Initializează mâncarea la o poziție aleatoare și o marchează activă
    def __init__(self):
        self.position = pygame.math.Vector2(random.uniform(0, SCREEN_WIDTH), random.uniform(0, SCREEN_HEIGHT))
        self.active = True
    def draw(self):
        
        pygame.draw.rect(screen, COLOR_FOOD, (self.position.x, self.position.y,4,4))


class Agent:
    """Base class for all agents in the simulation."""
    # Inițializează agentul: poziție, viteză, viteză de bază, culoare, energie și stare
    def __init__(self, position=None, velocity=None, speed=1.2, color=COLOR_PREY):
        self.position = position or pygame.math.Vector2(random.uniform(0, SCREEN_WIDTH), random.uniform(0, SCREEN_HEIGHT))
        self.velocity = velocity or pygame.math.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize()   
        self.base_speed = speed
        self.speed = speed
        self.color = color
        self.trail = []
        self.max_trail_length = 10
        self.base_color = color

        self.state = "ACTIVE" # ACTIVE, SEEKING_MATE, MATING
        self.mating_timer = 0
        self.mating_partener = None

        self.energy = ENERGY_START
        self.alive = True

    def update_position(self):
        """Update the agent's position based on its velocity and speed."""
        if self.state == "MATING":
            return  # Nu se misca in timpul imperecherii 
        
        self.energy -= ENERGY_LOSS_PER_FRAME
        
        if self.energy <= 0:
            self.alive = False
            return
        
        self.speed = min(self.speed, 3)
        self.position += self.velocity * self.speed
        self._bounce_off_walls()
        self._update_trail()

    def avoid_obstacles(self, obstacles):
        """Adjust velocity to avoid obstacles."""
        steering = pygame.math.Vector2(0, 0)
        for obs in obstacles:
            distance = self.position.distance_to(obs.position)
            # Zona de siguranță = Raza obstacolului + 30px margine
            if distance < obs.radius + 30:
                # Vectorul care împinge agentul DEPARTE de centrul obstacolului
                diff = self.position - obs.position
                if diff.length() > 0:
                    # Cu cât e mai aproape, cu atât împinge mai tare
                    steering += diff.normalize() / distance 
        
        if steering.length() > 0:
            steering = steering.normalize() * OBSTACLE_AVOID_WEIGHT
        return steering

    def start_mating(self, partner):
        """Initiate the mating process with a partner agent."""
        self.state = "MATING"
        self.mating_timer = MATING_FRAMES
        self.velocity = pygame.math.Vector2(0, 0)
        self.color = COLOR_MATING_ACTION
        self.mating_partner = partner
    
    def finish_mating(self):
        """Complete the mating process and produce offspring."""
        child = None

        self.energy -= ENERGY_REPRODUCE_COST
        self.state = "ACTIVE"
        self.color = self.base_color

        if self.mating_partner and id(self) > id(self.mating_partner):
            offset_x = random.choice([-40, 40])
            offset_y = random.choice([-40, 40])
            spawn_pos = self.position + pygame.math.Vector2(offset_x, offset_y)

            spawn_pos.x = max(0, min(spawn_pos.x, SCREEN_WIDTH))
            spawn_pos.y = max(0, min(spawn_pos.y, SCREEN_HEIGHT))

            child = self.__class__(position=spawn_pos)

        self.mating_partner = None
        return child
    
    def handle_reproduction(self, partner):
        """Handle the reproduction process with a partner agent."""
        child = None
        if self.state == "ACTIVE" and self.energy >= ENERGY_TO_REPRODUCE:
            self.state = "SEEKING_MATE"
            self.color = COLOR_MATING

        if self.state == "SEEKING_MATE" and self.energy < ENERGY_TO_REPRODUCE:
            self.state = "ACTIVE"
            self.color = self.base_color

        if self.state == "SEEKING_MATE":
            potential_partners = [p for p in partner if p is not self and p.state == "SEEKING_MATE"]
            if potential_partners:
                nearest_partner = min(potential_partners, key=lambda p: self.position.distance_to(p.position))
                dir_vec = nearest_partner.position - self.position
                if dir_vec.length() > 0:
                    self.velocity = dir_vec.normalize()

                if self.position.distance_to(nearest_partner.position) < 10:
                    self.start_mating(nearest_partner)
                    nearest_partner.start_mating(self)
        if self.state == "MATING":
            self.mating_timer -= 1
            if self.mating_timer <= 0:
                child = self.finish_mating()
        return child

    def _bounce_off_walls(self):
        """Bounce the agent off the screen edges."""
        if self.position.x < 0 or self.position.x > SCREEN_WIDTH:
            self.velocity.x *= -1
        if self.position.y < 0 or self.position.y > SCREEN_HEIGHT:
            self.velocity.y *= -1

        # Keep position within bounds
        self.position.x = max(0, min(self.position.x, SCREEN_WIDTH))
        self.position.y = max(0, min(self.position.y, SCREEN_HEIGHT))

    #update traseu
    def _update_trail(self):
        """Update the trail of the agent for visualization."""
        self.trail.append(self.position.copy())
        if len(self.trail) > self.max_trail_length:
            self.trail.pop(0)

    #desenam traseu
    def draw_trail(self):
        """Draw the trail of the agent."""
        if len(self.trail) > 1:
            pygame.draw.lines(screen, self.color, False, [(int(p.x), int(p.y)) for p in self.trail], 1)

    def draw(self):
        """Method to draw the agent. To be implemented by subclasses."""
        raise NotImplementedError("Draw method must be implemented by subclasses.")

class Prey(Agent):
    """Class representing a prey agent."""
    # Creează o pradă cu viteză și rază de vizibilitate
    def __init__(self,position=None):
        super().__init__(position=position, speed=SPEED_PREY, color=COLOR_PREY)
        self.vision_radius = 50  # Detection radius for predators
    
    def apply_flocking(self, all_prey):
        """Apply flocking behavior based on nearby prey."""
        steering = pygame.math.Vector2(0, 0)
        separation = pygame.math.Vector2(0, 0)
        alignment = pygame.math.Vector2(0, 0)
        cohesion = pygame.math.Vector2(0, 0)

        total = 0
        center_of_mass = pygame.math.Vector2(0, 0)

        for other in all_prey:
            if total >= FLOCK_MAX_NEIGHBORS:
                break
            if other is not self and other.alive:
                distance = self.position.distance_to(other.position)
                if distance < FLOCK_DETECTION_RADIUS:
                    total += 1

                    safe_distance = max(distance, 2.0)
                    # Separation
                    if distance > 0:
                        diff = self.position - other.position
                        diff /= safe_distance  
                        separation += diff
                    
                    # Aliniere
                    alignment += other.velocity

                    # Coeziune
                    center_of_mass += other.position
        if total > 0:
            if separation.length() > 0:
                separation = separation.normalize() * FLOCK_SEPARATION_WEIGHT
            
            alignment /= total
            if alignment.length() > 0:
                alignment = alignment.normalize() * FLOCK_ALIGNMENT_WEIGHT

            center_of_mass /= total
            cohesion = center_of_mass - self.position
            if cohesion.length() > 0:
                cohesion = cohesion.normalize() * FLOCK_COHESION_WEIGHT
            
            steering = separation + alignment + cohesion

            flock_speed_boost = 1 + (total * 0.1)
            self.speed = self.base_speed * flock_speed_boost
        else:
            self.speed = self.base_speed
        return steering

    def update(self, predators, other_prey, food_list, obstacles, flocking_enabled):
        """Update the prey's state based on nearby predators."""
        if not self.alive: return None
        child = None

        if self.state == "MATING":
            child = self.handle_reproduction(other_prey)
            self.update_position()
            return child
        
        obstacle_avoidance = self.avoid_obstacles(obstacles)

        #fugi de pradatori chiar daca vrei sa te reproduci
        nearest_predator = self._find_nearest_predator(predators)
        if nearest_predator and self.position.distance_to(nearest_predator.position) < self.vision_radius:
                self.state = "ACTIVE"
                self.flee_from(nearest_predator)
                self.color = self.base_color
                if obstacle_avoidance.length() > 0:
                    self.velocity += obstacle_avoidance
                    self.velocity = self.velocity.normalize()
        else:
            if self.energy >= ENERGY_TO_REPRODUCE or self.state == "SEEKING_MATE":
                child = self.handle_reproduction(other_prey)

                if self.state == "SEEKING_MATE" and obstacle_avoidance.length() > 0:
                    self.velocity += obstacle_avoidance
                    self.velocity = self.velocity.normalize()
            elif self.state == "ACTIVE":
                flock_vector = pygame.math.Vector2(0, 0)
                if flocking_enabled:
                    flock_vector = self.apply_flocking(other_prey)
                food_vector = pygame.math.Vector2(0, 0)

                if self.energy < ENERGY_TO_REPRODUCE:
                    nearest_food = self.find_nearest_food(food_list)
                    if nearest_food:
                        if self.position.distance_to(nearest_food.position) < 5:
                            nearest_food.active = False
                            self.energy = min(self.energy + ENERGY_FROM_FOOD, ENERGY_MAX)
                        else:
                            food_direction = nearest_food.position - self.position
                            if food_direction.length() > 0:
                                food_vector = food_direction.normalize() * 1.5  # Ponderea pentru direcția către mâncare
                
                final_dir = self.velocity + obstacle_avoidance + flock_vector + food_vector
                if final_dir.length() > 0:
                    self.velocity = final_dir.normalize()

        self.update_position()
        return child

    def _find_nearest_predator(self, predators):
        """Find the nearest predator within vision radius."""
        nearest = None
        min_distance = self.vision_radius
        for predator in predators:
            distance = self.position.distance_to(predator.position)
            if distance < min_distance:
                min_distance = distance
                nearest = predator
        return nearest

    def find_nearest_food(self, food_list):
        # Return nearest active food within a reasonable search radius
        active_food = [f for f in food_list if f.active]
        if not active_food: return None
        nearest = min(active_food, key = lambda f: self.position.distance_to(f.position))
        if self.position.distance_to(nearest.position) < self.vision_radius * 2:
            return nearest
        
        return None
    
    def flee_from(self, predator):
        """Change velocity to flee away from the predator."""
        dir_vec = self.position - predator.position
        if dir_vec.length() > 0:
            self.velocity = dir_vec.normalize()

    def draw(self):
        """Draw the prey as a circle with its trail."""
        pygame.draw.circle(screen, self.color, (int(self.position.x), int(self.position.y)), 4)
        self.draw_trail()



class Predator(Agent):
    """Class representing a predator agent."""
    # Creează un prădător cu viteză și aspect
    def __init__(self, position=None):
        super().__init__(position=position, speed=SPEED_PREDATOR, color=COLOR_PREDATOR)

    def update(self, prey_list, other_predators, obstacles):
        """Update the predator's state based on nearby prey."""
        if not self.alive: return None
        child = None
        avoid_vec = self.avoid_obstacles(obstacles)
        child = self.handle_reproduction(other_predators)

        if self.state == "SEEKING_MATE":
            if avoid_vec.length() > 0:
                self.velocity += avoid_vec
                self.velocity = self.velocity.normalize()
            self.update_position()
        else:
            nearest_prey = self._find_nearest_prey(prey_list)
            if nearest_prey:
                self.hunt(nearest_prey)
                if avoid_vec.length() > 0:
                    self.velocity += avoid_vec
                    self.velocity = self.velocity.normalize()
            else: 
                if avoid_vec.length() > 0:
                    self.velocity += avoid_vec
                    self.velocity = self.velocity.normalize()
                self.update_position()
        return child
    
    def _find_nearest_prey(self, prey_list):
        """Find the nearest prey."""
        return min(prey_list, key=lambda prey: self.position.distance_to(prey.position), default=None)

    def hunt(self, prey):
        """Change velocity to move towards the prey."""
        dir_vec = prey.position - self.position
        if dir_vec.length() > 0:
            self.velocity = dir_vec.normalize()
        self.update_position()
        self.energy -= 0.1

    def draw(self):
        """Draw the predator as a rotated triangle with its trail."""
        # Calculate the angle in degrees between the velocity and the x-axis
        angle = self.velocity.angle_to(pygame.math.Vector2(1, 0))

        # Define the triangle points relative to the origin, pointing right
        point_list = [
            pygame.math.Vector2(10, 0),   # Tip of the triangle
            pygame.math.Vector2(-5, -5),  # Bottom left
            pygame.math.Vector2(-5, 5),   # Top left
        ]

        # Rotate the points and translate to the predator's position
        rotated_points = [self.position + p.rotate(-angle) for p in point_list]

        # Draw the predator as a triangle
        pygame.draw.polygon(screen, self.color, rotated_points)

        # Draw the trail
        self.draw_trail()

class Simulation:
    """Class to manage the entire simulation."""
    # Inițializează simularea: agenți, obstacole, hrana etc
    def __init__(self, num_prey=25, num_predators=5):
        self.prey_list = [Prey() for _ in range(num_prey)]
        self.predator_list = [Predator() for _ in range(num_predators)]
        self.obstacles = [Obstacle() for _ in range(NUM_OBSTACLES)]
        self.food_list = []
        for _ in range(INITIAL_FOOD_COUNT):
            self.spawn_safe_food()

        self.history_prey = []
        self.history_predators = []
        self.history_prey_births = []
        self.history_predator_births = []
        self.time_steps = []
        self.freame_count = 0

        self.running = True
        self.flocking_enabled = True

    #mancarea sigura departe de obstacole
    def spawn_safe_food(self):
        """Spawn food away from obstacles."""
        for _ in range(10):
            potential_pos = pygame.math.Vector2(
                random.uniform(0, SCREEN_WIDTH), 
                random.uniform(0, SCREEN_HEIGHT)
            )

            safe = True
            for obs in self.obstacles:
                if potential_pos.distance_to(obs.position) < obs.radius + 35:
                    safe = False
                    break
            
            if safe:
                new_food = Food()
                new_food.position = potential_pos
                self.food_list.append(new_food)
                return 

    def plot_data(self):
        """Generate and show plots for simulation history."""
        # Set a pink background for figure and axes, and use black for text/borders
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        pink_bg = "#f5c0ff"  # light pink
        fig.patch.set_facecolor(pink_bg)
        ax1.set_facecolor(pink_bg)
        ax2.set_facecolor(pink_bg)

        # GRAFIC 1: Populația Totală
        # Prey = red, Predators = green
        ax1.plot(self.time_steps, self.history_prey, label='Prey', color='red')
        ax1.plot(self.time_steps, self.history_predators, label='Predators', color='green')
        ax1.set_title('Population Change Over Time')
        ax1.set_ylabel('Count')
        ax1.legend(facecolor=pink_bg, edgecolor='black')
        ax1.grid(True, color='black', alpha=0.15)

        # GRAFIC 2: Rata Natalității (Nasteri pe frame)
        # Use softer shades for birth events to match main colors
        ax2.plot(self.time_steps, self.history_prey_births, label='Prey Births', color='#ff0033', alpha=0.8, linewidth=0.6)
        ax2.plot(self.time_steps, self.history_predator_births, label='Predator Births', color='#00cc44', alpha=0.8, linewidth=0.6)
        ax2.set_title('Birth Events')
        ax2.set_xlabel('Time (Frames)')
        ax2.set_ylabel('Newborns per Frame')
        ax2.legend(facecolor=pink_bg, edgecolor='black')
        ax2.grid(True, color='black', alpha=0.15)

        # Make text, labels, ticks and spines black for contrast
        for ax in (ax1, ax2):
            ax.title.set_color('black')
            ax.xaxis.label.set_color('black')
            ax.yaxis.label.set_color('black')
            ax.tick_params(colors='black')
            for spine in ax.spines.values():
                spine.set_edgecolor('black')

        backend = matplotlib.get_backend()
        plt.tight_layout()
        if 'Agg' in backend:
            out_file = 'simulation_plots.png'
            print(f"Saving graphs to {out_file} (headless backend: {backend})")
            plt.savefig(out_file)
        else:
            print(f"Using GUI backend ({backend}) — displaying graphs interactively.")
            plt.show()

    def run(self):
        """Main loop of the simulation."""
        while self.running:
            clock.tick(FRAME_RATE)
            self.handle_events()
            self.update_agents()
            self.handle_collisions()
            self.render()

        pygame.quit()
        self.plot_data()

    def handle_events(self):
        """Handle user input and events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click to add food
                    mouse_pos = pygame.math.Vector2(event.pos)
                    is_safe_click = True
                    for obs in self.obstacles:
                        if mouse_pos.distance_to(obs.position) < obs.radius + 20:
                            is_safe_click = False
                            break
                    if is_safe_click:
                        new_food = Food()
                        new_food.position = mouse_pos
                        self.food_list.append(new_food)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    self.add_prey()
                elif event.key == pygame.K_o:
                    self.add_predator()
                elif event.key == pygame.K_f:
                    self.food_list.append(Food())
                elif event.key == pygame.K_b:
                    self.flocking_enabled = not self.flocking_enabled

    def add_prey(self):
        """Add a new prey to the simulation."""
        self.prey_list.append(Prey())

    def add_predator(self):
        """Add a new predator to the simulation."""
        self.predator_list.append(Predator())

    def update_agents(self):
        """Update all agents in the simulation."""

        while len(self.food_list) < INITIAL_FOOD_COUNT:
            self.spawn_safe_food()
        
        new_prey = []
        for prey in self.prey_list[:]:
            child = prey.update(self.predator_list, self.prey_list, self.food_list, self.obstacles, self.flocking_enabled)
            if child:
                new_prey.append(child)
        if new_prey:
            self.prey_list.extend(new_prey)

        new_predators = []
        for predator in self.predator_list[:]:
            child = predator.update(self.prey_list, self.predator_list,self.obstacles)
            if child:
                new_predators.append(child)
        if new_predators:
            self.predator_list.extend(new_predators)

        self.history_prey.append(len(self.prey_list))
        self.history_predators.append(len(self.predator_list))
        self.history_prey_births.append(len(new_prey))
        self.history_predator_births.append(len(new_predators))
        self.time_steps.append(self.freame_count)
        self.freame_count += 1

    def handle_collisions(self):
        """Handle collisions between predators and prey."""
        for predator in self.predator_list:
            if not predator.alive or predator.state == "MATING": continue

            for prey in self.prey_list[:]:
                if prey.alive and predator.position.distance_to(prey.position) < 5:
                    self.prey_list.remove(prey)
                    prey.alive = False
                    predator.energy = min(predator.energy + ENERGY_FROM_PREY, ENERGY_MAX)

        #stergem pe cei care au murit de foame si mancarea mancata deja
        self.prey_list = [p for p in self.prey_list if p.alive]
        self.predator_list = [p for p in self.predator_list if p.alive]
        self.food_list = [f for f in self.food_list if f.active]

    def render(self):
        """Render all elements on the screen."""
        screen.fill(COLOR_BG)

        for food in self.food_list:
            food.draw()

        for obstacle in self.obstacles:
            obstacle.draw()

        self.draw_legend()
        self.draw_stats()

        # Draw all prey
        for prey in self.prey_list:
            prey.draw()

        # Draw all predators
        for predator in self.predator_list:
            predator.draw()

        pygame.display.flip()

    def draw_legend(self):
        """Draw the legend on the screen."""
        prey_text = FONT.render('Prey (Green Circle) - Press P to add', True, COLOR_PREY)
        predator_text = FONT.render('Predator (Red Triangle) - Press O to add', True, COLOR_PREDATOR)
        food_text = FONT.render('Food (Pink Dot) - Press F to add', True, COLOR_FOOD) 
        screen.blit(prey_text, (10, 10))
        screen.blit(predator_text, (10, 30))
        screen.blit(food_text,(10, 50))

        if self.flocking_enabled:
            flock_status = "ON"
            status_color = (0, 255, 0) 
        else:
            flock_status = "OFF"
            status_color = (255, 50, 50) 

        # Construim textul
        controls_str = f"Controls: Click = Add Food | B = Flocking(ingramadire): {flock_status}"
        controls_surface = FONT.render(controls_str, True, (200, 200, 200))
        screen.blit(controls_surface,(10,70))

    def draw_stats(self):
        """Draw the simulation statistics on the screen."""
        prey_count_text = FONT.render(f'Prey Count: {len(self.prey_list)}', True, COLOR_TEXT)
        predator_count_text = FONT.render(f'Predator Count: {len(self.predator_list)}', True, COLOR_TEXT)
        screen.blit(prey_count_text, (SCREEN_WIDTH - 150, 10))
        screen.blit(predator_count_text, (SCREEN_WIDTH - 150, 30))

if __name__== "__main__":
    simulation = Simulation()
    simulation.run()